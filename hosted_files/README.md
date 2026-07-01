# Hosted Files Directory

This directory is used for secure file hosting through the Flask application.

## Usage

Files placed in this directory (or subdirectories) can be accessed via:
```
http://your-domain.com/files/filename.ext
http://your-domain.com/files/subdirectory/filename.ext
http://your-domain.com/files/path/to/file.ext
```

## Security Features

The file serving route implements multiple security measures:

1. **Path Traversal Prevention**: Blocks any use of `..` in paths to prevent going up directories
2. **Directory Boundary Enforcement**: Uses realpath verification to ensure files are within this directory
3. **Symlink Protection**: Resolves symlinks to verify actual file location
4. **Directory Depth**: Allows access to subdirectories but only within hosted_files/
5. **Path Normalization**: Handles both forward and backslashes correctly
6. **Non-executable**: Files are served with `as_attachment=False` for inline viewing

## Examples

### Valid Requests
- `/files/document.pdf` → Serves `document.pdf`
- `/files/images/photo.png` → Serves `images/photo.png`
- `/files/docs/2024/report.pdf` → Serves `docs/2024/report.pdf`
- `/files/data/json/config.json` → Serves `data/json/config.json`

### Blocked Requests
- `/files/../config.py` → 403 Forbidden (directory traversal)
- `/files/docs/../../alice_app.py` → 403 Forbidden (path escape)
- `/files/../../../etc/passwd` → 403 Forbidden (path escape)
- `/files/subdir/../../../secret` → 403 Forbidden (contains ..)

## Directory Structure Example

```
hosted_files/
├── README.md
├── example.txt
├── images/
│   ├── photo1.jpg
│   └── photo2.png
├── documents/
│   ├── 2024/
│   │   └── report.pdf
│   └── archive/
│       └── old.txt
└── data/
    └── export.csv
```

## Notes

- Subdirectories are fully supported and accessible
- The `..` operator is completely blocked
- All path components are normalized for security
- File names and paths are automatically validated
- All access attempts are logged
- Directory listing is not supported (must know exact file path)
