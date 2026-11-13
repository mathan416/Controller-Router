import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('emulator_builder',root/'emulator-patches/build.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class EmulatorBuilderTests(unittest.TestCase):
    def test_gsplus_expected_binary_and_user_cmake_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'source';f=source/'gsplus/src/sdl_driver.c'
            f.parent.mkdir(parents=True);f.write_bytes(b'pinned')
            destination=base/'build';calls=[]
            def fake_run(command, **kwargs):
                calls.append(command)
                if command[:2]==['cmake','--build']:
                    binary=destination/'router-build/gsplus';binary.parent.mkdir(parents=True);binary.touch()
            with patch.dict(builder.PROFILES,{'gsplus':('gsplus/src/sdl_driver.c',hashlib.sha256(b'pinned').hexdigest())}), patch.object(builder.subprocess,'run',side_effect=fake_run):
                result=builder.build('gsplus',source,destination,2,['-DSDL_X11=OFF'])
            self.assertEqual(result,(destination/'router-build/gsplus').resolve())
            self.assertIn('-DSDL_X11=OFF',calls[1]); self.assertEqual(f.read_bytes(),b'pinned')

    def test_rejects_modified_source_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'src';p=source/'SDL/DispKbd.c';p.parent.mkdir(parents=True);p.write_text('wrong')
            with self.assertRaisesRegex(ValueError,'source|Source'):
                builder.build('arcem',source,root/'dest')
            (root/'dest').mkdir()
            with self.assertRaisesRegex(ValueError,'already exists'):
                builder.build('arcem',source,root/'dest')
