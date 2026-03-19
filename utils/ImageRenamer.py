import os
import sys
from pathlib import Path
from typing import List, Tuple


def get_image_files(folder_path: str) -> List[str]:
    """
    Get all image files from the specified folder, sorted alphabetically.

    Args:
        folder_path: Path to the folder containing images

    Returns:
        Sorted list of image file paths
    """
    # Supported image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

    image_files = []
    for file in os.listdir(folder_path):
        if Path(file).suffix.lower() in image_extensions:
            image_files.append(os.path.join(folder_path, file))

    # Sort alphabetically for consistent ordering
    image_files.sort()

    return image_files


def preview_renames(image_files: List[str], prefix: str) -> List[Tuple[str, str]]:
    """
    Generate preview of old and new filenames.

    Args:
        image_files: List of image file paths
        prefix: Prefix for new filenames

    Returns:
        List of tuples (old_path, new_path)
    """
    rename_plan = []

    for idx, img_path in enumerate(image_files, start=1):
        folder = os.path.dirname(img_path)
        extension = Path(img_path).suffix
        new_filename = f"{prefix} - {idx}{extension}"
        new_path = os.path.join(folder, new_filename)
        rename_plan.append((img_path, new_path))

    return rename_plan


def check_conflicts(rename_plan: List[Tuple[str, str]]) -> List[str]:
    """
    Check if any new filenames would overwrite existing files.

    Args:
        rename_plan: List of (old_path, new_path) tuples

    Returns:
        List of conflicting new paths
    """
    old_paths = {old for old, new in rename_plan}
    conflicts = []

    for old_path, new_path in rename_plan:
        # Check if new path exists and is not one of the files being renamed
        if os.path.exists(new_path) and new_path not in old_paths:
            conflicts.append(new_path)

    return conflicts


def rename_images(folder_path: str, prefix: str, auto_confirm: bool = False):
    """
    Rename all images in a folder with a prefix and sequential numbering.

    Args:
        folder_path: Path to folder containing images to rename
        prefix: Prefix for new filenames
        auto_confirm: If True, skip confirmation prompt
    """
    # Validate input folder
    if not os.path.exists(folder_path):
        print(f"Error: Folder '{folder_path}' does not exist.")
        return

    if not os.path.isdir(folder_path):
        print(f"Error: '{folder_path}' is not a directory.")
        return

    # Validate prefix
    if not prefix or not prefix.strip():
        print("Error: Prefix cannot be empty.")
        return

    prefix = prefix.strip()

    # Get all image files
    image_files = get_image_files(folder_path)

    if not image_files:
        print(f"No image files found in '{folder_path}'")
        return

    print(f"Found {len(image_files)} image(s) to rename")
    print(f"Folder: {folder_path}")
    print(f"Prefix: '{prefix}'")
    print("-" * 70)

    # Generate rename plan
    rename_plan = preview_renames(image_files, prefix)

    # Check for conflicts
    conflicts = check_conflicts(rename_plan)
    if conflicts:
        print("⚠ WARNING: The following files would be overwritten:")
        for conflict in conflicts:
            print(f"  - {os.path.basename(conflict)}")
        print("\nPlease move or rename these files first, or choose a different prefix.")
        return

    # Show preview
    print("Preview of changes:")
    for old_path, new_path in rename_plan[:10]:  # Show first 10
        old_name = os.path.basename(old_path)
        new_name = os.path.basename(new_path)
        print(f"  {old_name} → {new_name}")

    if len(rename_plan) > 10:
        print(f"  ... and {len(rename_plan) - 10} more files")

    print("-" * 70)

    # Confirm with user
    if not auto_confirm:
        response = input("Proceed with renaming? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Renaming cancelled.")
            return

    # Perform renaming with two-pass approach to avoid conflicts
    # First pass: rename to temporary names
    temp_renames = []
    for idx, (old_path, new_path) in enumerate(rename_plan):
        folder = os.path.dirname(old_path)
        extension = Path(old_path).suffix
        temp_name = f"__temp_rename_{idx}{extension}"
        temp_path = os.path.join(folder, temp_name)
        temp_renames.append((old_path, temp_path, new_path))

    # Execute first pass
    print("\nRenaming in progress...")
    successful = 0
    failed = 0

    try:
        # Step 1: Rename to temporary names
        for old_path, temp_path, new_path in temp_renames:
            try:
                os.rename(old_path, temp_path)
            except Exception as e:
                print(f"✗ Error renaming {os.path.basename(old_path)}: {str(e)}")
                failed += 1
                # If we fail here, we need to rollback
                raise

        # Step 2: Rename from temporary to final names
        for old_path, temp_path, new_path in temp_renames:
            try:
                os.rename(temp_path, new_path)
                successful += 1
            except Exception as e:
                print(f"✗ Error renaming to {os.path.basename(new_path)}: {str(e)}")
                failed += 1
                # If we fail here, we should try to continue but note the error

        # Summary
        print("-" * 70)
        print("Renaming complete!")
        print(f"Successfully renamed: {successful}")
        if failed > 0:
            print(f"Failed: {failed}")
        print(f"Total: {len(image_files)}")

    except Exception as e:
        print(f"\n⚠ Critical error during renaming: {str(e)}")
        print("Attempting to rollback changes...")

        # Rollback: try to restore original names
        for old_path, temp_path, new_path in temp_renames:
            try:
                if os.path.exists(temp_path):
                    os.rename(temp_path, old_path)
            except:
                pass

        print("Rollback attempted. Please check your files.")


def main():
    """Main function to run the image renamer."""
    print("=" * 70)
    print("Image Batch Renamer - Sequential Numbering")
    print("=" * 70)

    # Get folder path
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = input("Enter the folder path containing images: ").strip()
        folder_path = folder_path.strip('"').strip("'")

    # Get prefix
    if len(sys.argv) > 2:
        prefix = sys.argv[2]
        auto_confirm = len(sys.argv) > 3 and sys.argv[3] in ['-y', '--yes']
    else:
        prefix = input("Enter the prefix for renamed files: ").strip()
        auto_confirm = False

    # Rename images
    rename_images(folder_path, prefix, auto_confirm)


if __name__ == "__main__":
    main()