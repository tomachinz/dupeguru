# Copyright 2016 Hardcoded Software (http://www.hardcoded.net)
#
# This software is licensed under the "GPLv3" License as described in the "LICENSE" file,
# which should be included with this package. The terms are also available at
# http://www.gnu.org/licenses/gpl-3.0.html

from hscommon.jobprogress import job
from hscommon.path import Path
from hscommon.testutil import eq_

from .. import fs
from ..engine import getwords, Match
from ..ignore import IgnoreList
from ..scanner import Scanner, ScanType
from ..me.scanner import ScannerME
import pytest

class NamedObject:
    def __init__(self, name="foobar", size=1, path=None):
        if path is None:
            path = Path(name)
        else:
            path = Path(path)[name]
        self.name = name
        self.size = size
        self.path = path
        self.words = getwords(name)

    def __repr__(self):
        return '<NamedObject %r %r>' % (self.name, self.path)


no = NamedObject

@pytest.fixture
def fake_fileexists(request):
    # This is a hack to avoid invalidating all previous tests since the scanner started to test
    # for file existence before doing the match grouping.
    monkeypatch = request.getfixturevalue('monkeypatch')
    monkeypatch.setattr(Path, 'exists', lambda _: True)

def test_empty(fake_fileexists):
    s = Scanner()
    r = s.get_dupe_groups([])
    eq_(r, [])

def test_default_settings(fake_fileexists):
    s = Scanner()
    eq_(s.min_match_percentage, 80)
    eq_(s.scan_type, ScanType.Filename)
    eq_(s.mix_file_kind, True)
    eq_(s.word_weighting, False)
    eq_(s.match_similar_words, False)

def test_simple_with_default_settings(fake_fileexists):
    s = Scanner()
    f = [no('foo bar', path='p1'), no('foo bar', path='p2'), no('foo bleh')]
    r = s.get_dupe_groups(f)
    eq_(len(r), 1)
    g = r[0]
    #'foo bleh' cannot be in the group because the default min match % is 80
    eq_(len(g), 2)
    assert g.ref in f[:2]
    assert g.dupes[0] in f[:2]

def test_simple_with_lower_min_match(fake_fileexists):
    s = Scanner()
    s.min_match_percentage = 50
    f = [no('foo bar', path='p1'), no('foo bar', path='p2'), no('foo bleh')]
    r = s.get_dupe_groups(f)
    eq_(len(r), 1)
    g = r[0]
    eq_(len(g), 3)

def test_trim_all_ref_groups(fake_fileexists):
    # When all files of a group are ref, don't include that group in the results, but also don't
    # count the files from that group as discarded.
    s = Scanner()
    f = [no('foo', path='p1'), no('foo', path='p2'), no('bar', path='p1'), no('bar', path='p2')]
    f[2].is_ref = True
    f[3].is_ref = True
    r = s.get_dupe_groups(f)
    eq_(len(r), 1)
    eq_(s.discarded_file_count, 0)

def test_priorize(fake_fileexists):
    s = Scanner()
    f = [no('foo', path='p1'), no('foo', path='p2'), no('bar', path='p1'), no('bar', path='p2')]
    f[1].size = 2
    f[2].size = 3
    f[3].is_ref = True
    r = s.get_dupe_groups(f)
    g1, g2 = r
    assert f[1] in (g1.ref, g2.ref)
    assert f[0] in (g1.dupes[0], g2.dupes[0])
    assert f[3] in (g1.ref, g2.ref)
    assert f[2] in (g1.dupes[0], g2.dupes[0])

def test_content_scan(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Contents
    f = [no('foo'), no('bar'), no('bleh')]
    f[0].md5 = f[0].md5partial = 'foobar'
    f[1].md5 = f[1].md5partial = 'foobar'
    f[2].md5 = f[2].md5partial = 'bleh'
    r = s.get_dupe_groups(f)
    eq_(len(r), 1)
    eq_(len(r[0]), 2)
    eq_(s.discarded_file_count, 0) # don't count the different md5 as discarded!

def test_content_scan_compare_sizes_first(fake_fileexists):
    class MyFile(no):
        @property
        def md5(file):
            raise AssertionError()

    s = Scanner()
    s.scan_type = ScanType.Contents
    f = [MyFile('foo', 1), MyFile('bar', 2)]
    eq_(len(s.get_dupe_groups(f)), 0)

def test_min_match_perc_doesnt_matter_for_content_scan(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Contents
    f = [no('foo'), no('bar'), no('bleh')]
    f[0].md5 = f[0].md5partial = 'foobar'
    f[1].md5 = f[1].md5partial = 'foobar'
    f[2].md5 = f[2].md5partial = 'bleh'
    s.min_match_percentage = 101
    r = s.get_dupe_groups(f)
    eq_(len(r), 1)
    eq_(len(r[0]), 2)
    s.min_match_percentage = 0
    r = s.get_dupe_groups(f)
    eq_(len(r), 1)
    eq_(len(r[0]), 2)

def test_content_scan_doesnt_put_md5_in_words_at_the_end(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Contents
    f = [no('foo'), no('bar')]
    f[0].md5 = f[0].md5partial = '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    f[1].md5 = f[1].md5partial = '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    r = s.get_dupe_groups(f)
    r[0]

def test_extension_is_not_counted_in_filename_scan(fake_fileexists):
    s = Scanner()
    s.min_match_percentage = 100
    f = [no('foo.bar'), no('foo.bleh')]
    r = s.get_dupe_groups(f)
    eq_(len(r), 1)
    eq_(len(r[0]), 2)

def test_job(fake_fileexists):
    def do_progress(progress, desc=''):
        log.append(progress)
        return True

    s = Scanner()
    log = []
    f = [no('foo bar'), no('foo bar'), no('foo bleh')]
    s.get_dupe_groups(f, j=job.Job(1, do_progress))
    eq_(log[0], 0)
    eq_(log[-1], 100)

def test_mix_file_kind(fake_fileexists):
    s = Scanner()
    s.mix_file_kind = False
    f = [no('foo.1'), no('foo.2')]
    r = s.get_dupe_groups(f)
    eq_(len(r), 0)

def test_word_weighting(fake_fileexists):
    s = Scanner()
    s.min_match_percentage = 75
    s.word_weighting = True
    f = [no('foo bar'), no('foo bar bleh')]
    r = s.get_dupe_groups(f)
    eq_(len(r), 1)
    g = r[0]
    m = g.get_match_of(g.dupes[0])
    eq_(m.percentage, 75) # 16 letters, 12 matching

def test_similar_words(fake_fileexists):
    s = Scanner()
    s.match_similar_words = True
    f = [no('The White Stripes'), no('The Whites Stripe'), no('Limp Bizkit'), no('Limp Bizkitt')]
    r = s.get_dupe_groups(f)
    eq_(len(r), 2)

def test_fields(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Fields
    f = [no('The White Stripes - Little Ghost'), no('The White Stripes - Little Acorn')]
    r = s.get_dupe_groups(f)
    eq_(len(r), 0)

def test_fields_no_order(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.FieldsNoOrder
    f = [no('The White Stripes - Little Ghost'), no('Little Ghost - The White Stripes')]
    r = s.get_dupe_groups(f)
    eq_(len(r), 1)

def test_tag_scan(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Tag
    o1 = no('foo')
    o2 = no('bar')
    o1.artist = 'The White Stripes'
    o1.title = 'The Air Near My Fingers'
    o2.artist = 'The White Stripes'
    o2.title = 'The Air Near My Fingers'
    r = s.get_dupe_groups([o1, o2])
    eq_(len(r), 1)

def test_tag_with_album_scan(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Tag
    s.scanned_tags = set(['artist', 'album', 'title'])
    o1 = no('foo')
    o2 = no('bar')
    o3 = no('bleh')
    o1.artist = 'The White Stripes'
    o1.title = 'The Air Near My Fingers'
    o1.album = 'Elephant'
    o2.artist = 'The White Stripes'
    o2.title = 'The Air Near My Fingers'
    o2.album = 'Elephant'
    o3.artist = 'The White Stripes'
    o3.title = 'The Air Near My Fingers'
    o3.album = 'foobar'
    r = s.get_dupe_groups([o1, o2, o3])
    eq_(len(r), 1)

def test_that_dash_in_tags_dont_create_new_fields(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Tag
    s.scanned_tags = set(['artist', 'album', 'title'])
    s.min_match_percentage = 50
    o1 = no('foo')
    o2 = no('bar')
    o1.artist = 'The White Stripes - a'
    o1.title = 'The Air Near My Fingers - a'
    o1.album = 'Elephant - a'
    o2.artist = 'The White Stripes - b'
    o2.title = 'The Air Near My Fingers - b'
    o2.album = 'Elephant - b'
    r = s.get_dupe_groups([o1, o2])
    eq_(len(r), 1)

def test_tag_scan_with_different_scanned(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Tag
    s.scanned_tags = set(['track', 'year'])
    o1 = no('foo')
    o2 = no('bar')
    o1.artist = 'The White Stripes'
    o1.title = 'some title'
    o1.track = 'foo'
    o1.year = 'bar'
    o2.artist = 'The White Stripes'
    o2.title = 'another title'
    o2.track = 'foo'
    o2.year = 'bar'
    r = s.get_dupe_groups([o1, o2])
    eq_(len(r), 1)

def test_tag_scan_only_scans_existing_tags(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Tag
    s.scanned_tags = set(['artist', 'foo'])
    o1 = no('foo')
    o2 = no('bar')
    o1.artist = 'The White Stripes'
    o1.foo = 'foo'
    o2.artist = 'The White Stripes'
    o2.foo = 'bar'
    r = s.get_dupe_groups([o1, o2])
    eq_(len(r), 1) # Because 'foo' is not scanned, they match

def test_tag_scan_converts_to_str(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Tag
    s.scanned_tags = set(['track'])
    o1 = no('foo')
    o2 = no('bar')
    o1.track = 42
    o2.track = 42
    try:
        r = s.get_dupe_groups([o1, o2])
    except TypeError:
        raise AssertionError()
    eq_(len(r), 1)

def test_tag_scan_non_ascii(fake_fileexists):
    s = Scanner()
    s.scan_type = ScanType.Tag
    s.scanned_tags = set(['title'])
    o1 = no('foo')
    o2 = no('bar')
    o1.title = 'foobar\u00e9'
    o2.title = 'foobar\u00e9'
    try:
        r = s.get_dupe_groups([o1, o2])
    except UnicodeEncodeError:
        raise AssertionError()
    eq_(len(r), 1)

def test_ignore_list(fake_fileexists):
    s = Scanner()
    f1 = no('foobar')
    f2 = no('foobar')
    f3 = no('foobar')
    f1.path = Path('dir1/foobar')
    f2.path = Path('dir2/foobar')
    f3.path = Path('dir3/foobar')
    ignore_list = IgnoreList()
    ignore_list.Ignore(str(f1.path), str(f2.path))
    ignore_list.Ignore(str(f1.path), str(f3.path))
    r = s.get_dupe_groups([f1, f2, f3], ignore_list=ignore_list)
    eq_(len(r), 1)
    g = r[0]
    eq_(len(g.dupes), 1)
    assert f1 not in g
    assert f2 in g
    assert f3 in g
    # Ignored matches are not counted as discarded
    eq_(s.discarded_file_count, 0)

def test_ignore_list_checks_for_unicode(fake_fileexists):
    #scanner was calling path_str for ignore list checks. Since the Path changes, it must
    #be unicode(path)
    s = Scanner()
    f1 = no('foobar')
    f2 = no('foobar')
    f3 = no('foobar')
    f1.path = Path('foo1\u00e9')
    f2.path = Path('foo2\u00e9')
    f3.path = Path('foo3\u00e9')
    ignore_list = IgnoreList()
    ignore_list.Ignore(str(f1.path), str(f2.path))
    ignore_list.Ignore(str(f1.path), str(f3.path))
    r = s.get_dupe_groups([f1, f2, f3], ignore_list=ignore_list)
    eq_(len(r), 1)
    g = r[0]
    eq_(len(g.dupes), 1)
    assert f1 not in g
    assert f2 in g
    assert f3 in g

def test_file_evaluates_to_false(fake_fileexists):
    # A very wrong way to use any() was added at some point, causing resulting group list
    # to be empty.
    class FalseNamedObject(NamedObject):
        def __bool__(self):
            return False


    s = Scanner()
    f1 = FalseNamedObject('foobar', path='p1')
    f2 = FalseNamedObject('foobar', path='p2')
    r = s.get_dupe_groups([f1, f2])
    eq_(len(r), 1)

def test_size_threshold(fake_fileexists):
    # Only file equal or higher than the size_threshold in size are scanned
    s = Scanner()
    f1 = no('foo', 1, path='p1')
    f2 = no('foo', 2, path='p2')
    f3 = no('foo', 3, path='p3')
    s.size_threshold = 2
    groups = s.get_dupe_groups([f1, f2, f3])
    eq_(len(groups), 1)
    [group] = groups
    eq_(len(group), 2)
    assert f1 not in group
    assert f2 in group
    assert f3 in group

def test_tie_breaker_path_deepness(fake_fileexists):
    # If there is a tie in prioritization, path deepness is used as a tie breaker
    s = Scanner()
    o1, o2 = no('foo'), no('foo')
    o1.path = Path('foo')
    o2.path = Path('foo/bar')
    [group] = s.get_dupe_groups([o1, o2])
    assert group.ref is o2

def test_tie_breaker_copy(fake_fileexists):
    # if copy is in the words used (even if it has a deeper path), it becomes a dupe
    s = Scanner()
    o1, o2 = no('foo bar Copy'), no('foo bar')
    o1.path = Path('deeper/path')
    o2.path = Path('foo')
    [group] = s.get_dupe_groups([o1, o2])
    assert group.ref is o2

def test_tie_breaker_same_name_plus_digit(fake_fileexists):
    # if ref has the same words as dupe, but has some just one extra word which is a digit, it
    # becomes a dupe
    s = Scanner()
    o1 = no('foo bar 42')
    o2 = no('foo bar [42]')
    o3 = no('foo bar (42)')
    o4 = no('foo bar {42}')
    o5 = no('foo bar')
    # all numbered names have deeper paths, so they'll end up ref if the digits aren't correctly
    # used as tie breakers
    o1.path = Path('deeper/path')
    o2.path = Path('deeper/path')
    o3.path = Path('deeper/path')
    o4.path = Path('deeper/path')
    o5.path = Path('foo')
    [group] = s.get_dupe_groups([o1, o2, o3, o4, o5])
    assert group.ref is o5

def test_partial_group_match(fake_fileexists):
    # Count the number of discarded matches (when a file doesn't match all other dupes of the
    # group) in Scanner.discarded_file_count
    s = Scanner()
    o1, o2, o3 = no('a b'), no('a'), no('b')
    s.min_match_percentage = 50
    [group] = s.get_dupe_groups([o1, o2, o3])
    eq_(len(group), 2)
    assert o1 in group
    # The file that will actually be counted as a dupe is undefined. The only thing we want to test
    # is that we don't have both
    if o2 in group:
        assert o3 not in group
    else:
        assert o3 in group
    eq_(s.discarded_file_count, 1)

def test_dont_group_files_that_dont_exist(tmpdir):
    # when creating groups, check that files exist first. It's possible that these files have
    # been moved during the scan by the user.
    # In this test, we have to delete one of the files between the get_matches() part and the
    # get_groups() part.
    s = Scanner()
    s.scan_type = ScanType.Contents
    p = Path(str(tmpdir))
    p['file1'].open('w').write('foo')
    p['file2'].open('w').write('foo')
    file1, file2 = fs.get_files(p)

    def getmatches(*args, **kw):
        file2.path.remove()
        return [Match(file1, file2, 100)]

    s._getmatches = getmatches

    assert not s.get_dupe_groups([file1, file2])

def test_folder_scan_exclude_subfolder_matches(fake_fileexists):
    # when doing a Folders scan type, don't include matches for folders whose parent folder already
    # match.
    s = Scanner()
    s.scan_type = ScanType.Folders
    topf1 = no("top folder 1", size=42)
    topf1.md5 = topf1.md5partial = b"some_md5_1"
    topf1.path = Path('/topf1')
    topf2 = no("top folder 2", size=42)
    topf2.md5 = topf2.md5partial = b"some_md5_1"
    topf2.path = Path('/topf2')
    subf1 = no("sub folder 1", size=41)
    subf1.md5 = subf1.md5partial = b"some_md5_2"
    subf1.path = Path('/topf1/sub')
    subf2 = no("sub folder 2", size=41)
    subf2.md5 = subf2.md5partial = b"some_md5_2"
    subf2.path = Path('/topf2/sub')
    eq_(len(s.get_dupe_groups([topf1, topf2, subf1, subf2])), 1) # only top folders
    # however, if another folder matches a subfolder, keep in in the matches
    otherf = no("other folder", size=41)
    otherf.md5 = otherf.md5partial = b"some_md5_2"
    otherf.path = Path('/otherfolder')
    eq_(len(s.get_dupe_groups([topf1, topf2, subf1, subf2, otherf])), 2)

def test_ignore_files_with_same_path(fake_fileexists):
    # It's possible that the scanner is fed with two file instances pointing to the same path. One
    # of these files has to be ignored
    s = Scanner()
    f1 = no('foobar', path='path1/foobar')
    f2 = no('foobar', path='path1/foobar')
    eq_(s.get_dupe_groups([f1, f2]), [])

def test_dont_count_ref_files_as_discarded(fake_fileexists):
    # To speed up the scan, we don't bother comparing contents of files that are both ref files.
    # However, this causes problems in "discarded" counting and we make sure here that we don't
    # report discarded matches in exact duplicate scans.
    s = Scanner()
    s.scan_type = ScanType.Contents
    o1 = no("foo", path="p1")
    o2 = no("foo", path="p2")
    o3 = no("foo", path="p3")
    o1.md5 = o1.md5partial = 'foobar'
    o2.md5 = o2.md5partial = 'foobar'
    o3.md5 = o3.md5partial = 'foobar'
    o1.is_ref = True
    o2.is_ref = True
    eq_(len(s.get_dupe_groups([o1, o2, o3])), 1)
    eq_(s.discarded_file_count, 0)

def test_priorize_me(fake_fileexists):
    # in ScannerME, bitrate goes first (right after is_ref) in priorization
    s = ScannerME()
    o1, o2 = no('foo', path='p1'), no('foo', path='p2')
    o1.bitrate = 1
    o2.bitrate = 2
    [group] = s.get_dupe_groups([o1, o2])
    assert group.ref is o2

