"""Atomic writes clear the temporaries a killed writer left behind.

docker stop and installs end the portal with SIGTERM, which skips the
writer's own cleanup, so .connections.json.<random> files piled up on boards.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path

from router_shared import storage
from router_shared.pairing import write_json
from uno_portal.shared import pairing as portal_pairing


class StaleTemporaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'connections.json'
        old = time.time() - 3600
        self.stale = self.root / '.connections.json.3gyhnu_4'
        self.fresh = self.root / '.connections.json.q7f0ul4l'
        self.unrelated = [self.root / '.connections.json.backup', self.root / '.games.json.abcd1234',
                          self.root / 'before-connection-1.json']
        for path in [self.stale, self.fresh] + self.unrelated:
            path.write_text('{}')
        for path in [self.stale] + self.unrelated:
            os.utime(path, (old, old))

    def assert_cleaned(self):
        self.assertFalse(self.stale.exists())
        self.assertTrue(self.fresh.exists(), 'a temporary another writer may still own was removed')
        for path in self.unrelated:
            self.assertTrue(path.exists(), path.name)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),
                         sorted([self.target.name, self.fresh.name] + [p.name for p in self.unrelated]))

    def test_router_pairing_write_removes_old_leftovers(self):
        write_json(self.target, {'schema': 1})
        self.assert_cleaned()

    def test_portal_pairing_write_removes_old_leftovers(self):
        portal_pairing.write_json(self.target, {'schema': 1})
        self.assert_cleaned()

    def test_storage_write_removes_old_leftovers(self):
        storage.atomic_write(self.target, '{}\n')
        self.assert_cleaned()

    def test_symlinked_leftover_name_is_not_followed(self):
        outside = self.root / 'outside'
        outside.write_text('keep')
        link = self.root / '.connections.json.abcdefgh'
        link.symlink_to(outside)
        write_json(self.target, {})
        self.assertTrue(outside.exists())
        self.assertTrue(link.is_symlink())


if __name__ == '__main__':
    unittest.main()
