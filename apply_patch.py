import sys
import patch
import os

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python apply_patch.py <swift_file> <patch_file>')
        sys.exit(1)
    swift_file = sys.argv[1]
    patch_file = sys.argv[2]
    pset = patch.fromfile(patch_file)
    if not pset:
        print("Failed to parse patch file.")
        sys.exit(1)
    # The patch library applies patches relative to the current working directory
    # So we set root to the directory containing the swift file
    root_dir = os.path.dirname(os.path.abspath(swift_file))
    if pset.apply(root=root_dir):
        print("Patch applied successfully!")
    else:
        print("Failed to apply patch.")
        sys.exit(1)