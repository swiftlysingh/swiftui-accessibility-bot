import sys
import patch

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python apply_patch.py <swift_file> <patch_file>')
        sys.exit(1)
    swift_file = sys.argv[1]
    patch_file = sys.argv[2]
    pset = patch.fromfile(patch_file)
    if pset.apply():
        print("Patch applied successfully!")
    else:
        print("Failed to apply patch.")
        sys.exit(1)