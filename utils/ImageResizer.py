import cv2
import os
import sys
from pathlib import Path
from typing import List


def get_image_files(folder_path: str) -> List[str]:
    """
    Get all image files from the specified folder.

    Args:
        folder_path: Path to the folder containing images

    Returns:
        List of image file paths
    """
    # Supported image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

    image_files = []
    for file in os.listdir(folder_path):
        if Path(file).suffix.lower() in image_extensions:
            image_files.append(os.path.join(folder_path, file))

    return image_files


def generate_unique_filename(output_folder: str, base_name: str, extension: str) -> str:
    """
    Generate a unique filename to avoid overwriting existing files.

    Args:
        output_folder: Folder where file will be saved
        base_name: Base name for the file
        extension: File extension

    Returns:
        Unique filename
    """
    counter = 1
    filename = f"{base_name}{extension}"
    filepath = os.path.join(output_folder, filename)

    # If file exists, append a counter
    while os.path.exists(filepath):
        filename = f"{base_name}_{counter}{extension}"
        filepath = os.path.join(output_folder, filename)
        counter += 1

    return filename


def resize_images(input_folder: str, target_width: int = 1280, target_height: int = 720):
    """
    Resize all images in a folder to specified dimensions and save to a 'Converted' subfolder.

    Args:
        input_folder: Path to folder containing images to resize
        target_width: Target width in pixels (default: 1280)
        target_height: Target height in pixels (default: 720)
    """
    # Validate input folder
    if not os.path.exists(input_folder):
        print(f"Error: Folder '{input_folder}' does not exist.")
        return

    if not os.path.isdir(input_folder):
        print(f"Error: '{input_folder}' is not a directory.")
        return

    # Create output folder
    output_folder = os.path.join(input_folder, "Converted")
    os.makedirs(output_folder, exist_ok=True)

    # Get all image files
    image_files = get_image_files(input_folder)

    if not image_files:
        print(f"No image files found in '{input_folder}'")
        return

    print(f"Found {len(image_files)} image(s) to process")
    print(f"Output folder: {output_folder}")
    print(f"Target resolution: {target_width}x{target_height}")
    print("-" * 50)

    # Process each image
    successful = 0
    failed = 0

    for img_path in image_files:
        try:
            # Read image
            img = cv2.imread(img_path)

            if img is None:
                print(f"Failed to read: {os.path.basename(img_path)}")
                failed += 1
                continue

            # Get original dimensions
            original_height, original_width = img.shape[:2]

            # Resize image
            resized_img = cv2.resize(img, (target_width, target_height),
                                     interpolation=cv2.INTER_LANCZOS4)

            # Generate unique output filename
            base_name = Path(img_path).stem
            extension = Path(img_path).suffix
            unique_filename = generate_unique_filename(output_folder, base_name, extension)
            output_path = os.path.join(output_folder, unique_filename)

            # Save resized image
            cv2.imwrite(output_path, resized_img)

            print(f"✓ {os.path.basename(img_path)} ({original_width}x{original_height}) → {unique_filename}")
            successful += 1

        except Exception as e:
            print(f"✗ Error processing {os.path.basename(img_path)}: {str(e)}")
            failed += 1

    # Summary
    print("-" * 50)
    print(f"Processing complete!")
    print(f"Successfully converted: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(image_files)}")


def main():
    """Main function to run the image resizer."""
    print("=" * 50)
    print("Image Batch Resizer - Convert to 1280x720")
    print("=" * 50)

    # Get folder path from command line or user input
    if len(sys.argv) > 1:
        input_folder = sys.argv[1]
    else:
        input_folder = input("Enter the folder path containing images: ").strip()

        # Remove quotes if user copied path with quotes
        input_folder = input_folder.strip('"').strip("'")

    # Resize images
    resize_images(input_folder)


if __name__ == "__main__":
    main()