"""
Exact Python implementations of Leptonica's normalization functions.
Based on Leptonica 1.82+ source code.
"""

import numpy as np
from scipy.ndimage import (
    minimum_filter, maximum_filter, uniform_filter,
    grey_opening, grey_closing, grey_erosion, grey_dilation,
    gaussian_filter, rank_filter
)
from scipy.interpolate import RectBivariateSpline
import cv2


def rgb2gray(rgb: np.ndarray) -> np.ndarray:
    """Standard RGB → grayscale conversion."""
    if rgb.ndim == 2:
        return rgb
    return np.dot(rgb[..., :3], [0.299, 0.587, 0.114])


def ensure_float32(image: np.ndarray) -> np.ndarray:
    """Convert image to float32 in [0, 255] range."""
    img = image.copy()
    if img.dtype == np.uint8:
        return img.astype(np.float32)
    elif img.max() <= 1.0:
        return (img * 255.0).astype(np.float32)
    return img.astype(np.float32)


# =============================================================================
# 1. BACKGROUND NORMALIZATION
# =============================================================================

def pixBackgroundNorm(
        image: np.ndarray,
        sx: int = 10,
        sy: int = 10,
        thresh: int = 100,
        mincount: int = 50,
        bgval: int = 200,
        smoothx: int = 2,
        smoothy: int = 2
) -> np.ndarray:
    """
    Main background normalization - matches Leptonica's pixBackgroundNorm().

    Algorithm:
    1. Divide image into tiles of size (sx, sy)
    2. For each tile, compute mean if enough pixels > thresh
    3. Smooth the background map with Gaussian
    4. Normalize: output = input * bgval / background

    Args:
        image: Input grayscale image (uint8 or float)
        sx, sy: Tile size for background estimation
        thresh: Threshold for selecting background pixels
        mincount: Minimum pixels in tile to compute background
        bgval: Target background value (default 200)
        smoothx, smoothy: Smoothing kernel size for background map

    Returns:
        Normalized image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)
    h, w = gray.shape

    # Compute tile grid
    nx = (w + sx - 1) // sx
    ny = (h + sy - 1) // sy

    # Background map (will be smoothed later)
    bg_map = np.zeros((ny, nx), dtype=np.float32)

    # Compute background for each tile
    for j in range(ny):
        y_start = j * sy
        y_end = min((j + 1) * sy, h)

        for i in range(nx):
            x_start = i * sx
            x_end = min((i + 1) * sx, w)

            tile = gray[y_start:y_end, x_start:x_end]

            # Select pixels > thresh
            bright_pixels = tile[tile > thresh]

            if len(bright_pixels) >= mincount:
                bg_map[j, i] = np.mean(bright_pixels)
            else:
                # Use mean of all pixels if not enough bright ones
                bg_map[j, i] = np.mean(tile)

    # Smooth background map
    if smoothx > 0 or smoothy > 0:
        sigma_x = smoothx / 2.0
        sigma_y = smoothy / 2.0
        bg_map = gaussian_filter(bg_map, sigma=(sigma_y, sigma_x))

    # Interpolate background map to full image size
    x_coords = (np.arange(nx) + 0.5) * sx
    y_coords = (np.arange(ny) + 0.5) * sy

    interp = RectBivariateSpline(y_coords, x_coords, bg_map, kx=1, ky=1)

    x_full = np.arange(w)
    y_full = np.arange(h)
    bg_full = interp(y_full, x_full)

    # Normalize: output = input * bgval / background
    # Avoid division by zero
    bg_full = np.maximum(bg_full, 1.0)
    normalized = gray * bgval / bg_full
    normalized = np.clip(normalized, 0, 255)

    return normalized.astype(np.uint8)


def pixBackgroundNormSimple(
        image: np.ndarray,
        size: int = 50,
        bgval: int = 200
) -> np.ndarray:
    """
    Simplified background normalization - matches pixBackgroundNormSimple().

    Algorithm:
    1. Estimate background using morphological opening (erosion + dilation)
    2. Normalize: output = input * bgval / background

    Args:
        image: Input grayscale image
        size: Structuring element size (large = smoother background)
        bgval: Target background value

    Returns:
        Normalized image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Morphological opening to estimate background
    background = grey_opening(gray, size=size)

    # Avoid division by zero
    background = np.maximum(background, 1.0)

    # Normalize
    normalized = gray * bgval / background
    normalized = np.clip(normalized, 0, 255)

    return normalized.astype(np.uint8)


def pixBackgroundNormMorph(
        image: np.ndarray,
        size: int = 50,
        bgval: int = 200
) -> np.ndarray:
    """
    Morphological background normalization - matches pixBackgroundNormMorph().

    Uses closing (dilation + erosion) instead of opening.
    Better for dark objects on bright background.

    Args:
        image: Input grayscale image
        size: Structuring element size
        bgval: Target background value

    Returns:
        Normalized image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Morphological closing to estimate background
    background = grey_closing(gray, size=size)

    # Avoid division by zero
    background = np.maximum(background, 1.0)

    # Normalize
    normalized = gray * bgval / background
    normalized = np.clip(normalized, 0, 255)

    return normalized.astype(np.uint8)


def pixBackgroundNormFlex(
        image: np.ndarray,
        method: str = 'tile',  # 'tile' or 'morph'
        sx: int = 10,
        sy: int = 10,
        size: int = 50,
        thresh: int = 100,
        bgval: int = 200,
        smoothx: int = 2,
        smoothy: int = 2
) -> np.ndarray:
    """
    Flexible background normalization - combines tile and morphological methods.

    Args:
        method: 'tile' for tile-based, 'morph' for morphological
        (other params as in respective functions)

    Returns:
        Normalized image (uint8)
    """
    if method == 'morph':
        return pixBackgroundNormMorph(image, size=size, bgval=bgval)
    else:
        return pixBackgroundNorm(
            image, sx=sx, sy=sy, thresh=thresh,
            bgval=bgval, smoothx=smoothx, smoothy=smoothy
        )


# =============================================================================
# 2. CONTRAST NORMALIZATION
# =============================================================================

def pixContrastNorm(
        image: np.ndarray,
        sx: int = 10,
        sy: int = 10,
        mindiff: int = 50,
        smoothx: int = 2,
        smoothy: int = 2
) -> np.ndarray:
    """
    Standard contrast normalization - EXACT match to Leptonica's pixContrastNorm().

    Algorithm:
    1. Divide image into tiles
    2. Compute mean and stddev for each tile
    3. Smooth the mean and stddev maps
    4. Apply: output = (input - mean) / max(stddev, mindiff) * 64 + 128

    Args:
        image: Input grayscale image
        sx, sy: Tile size
        mindiff: Minimum stddev (prevents over-amplification in flat regions)
        smoothx, smoothy: Smoothing kernel size for mean/stddev maps

    Returns:
        Normalized image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)
    h, w = gray.shape

    # Compute tile grid
    nx = (w + sx - 1) // sx
    ny = (h + sy - 1) // sy

    # Mean and stddev maps
    mean_map = np.zeros((ny, nx), dtype=np.float32)
    std_map = np.zeros((ny, nx), dtype=np.float32)

    # Compute statistics for each tile
    for j in range(ny):
        y_start = j * sy
        y_end = min((j + 1) * sy, h)

        for i in range(nx):
            x_start = i * sx
            x_end = min((i + 1) * sx, w)

            tile = gray[y_start:y_end, x_start:x_end]

            mean_map[j, i] = np.mean(tile)
            std_map[j, i] = np.std(tile)

    # Smooth maps
    if smoothx > 0 or smoothy > 0:
        sigma_x = smoothx / 2.0
        sigma_y = smoothy / 2.0
        mean_map = gaussian_filter(mean_map, sigma=(sigma_y, sigma_x))
        std_map = gaussian_filter(std_map, sigma=(sigma_y, sigma_x))

    # Interpolate to full image size
    x_coords = (np.arange(nx) + 0.5) * sx
    y_coords = (np.arange(ny) + 0.5) * sy

    mean_interp = RectBivariateSpline(y_coords, x_coords, mean_map, kx=1, ky=1)
    std_interp = RectBivariateSpline(y_coords, x_coords, std_map, kx=1, ky=1)

    x_full = np.arange(w)
    y_full = np.arange(h)
    mean_full = mean_interp(y_full, x_full)
    std_full = std_interp(y_full, x_full)

    # Apply normalization: (input - mean) / max(std, mindiff) * target_std + target_mean
    # Leptonica uses target_std=64, target_mean=128
    std_full = np.maximum(std_full, mindiff)
    normalized = (gray - mean_full) / std_full * 64.0 + 128.0
    normalized = np.clip(normalized, 0, 255)

    return normalized.astype(np.uint8)


def pixContrastNormTo(
        image: np.ndarray,
        target_mean: float = 128.0,
        target_std: float = 64.0,
        sx: int = 10,
        sy: int = 10,
        mindiff: int = 50,
        smoothx: int = 2,
        smoothy: int = 2
) -> np.ndarray:
    """
    Contrast normalization to specific target mean/stddev.

    Same as pixContrastNorm but with custom targets.

    Args:
        target_mean: Target mean value (default 128)
        target_std: Target standard deviation (default 64)
        (other params as in pixContrastNorm)

    Returns:
        Normalized image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)
    h, w = gray.shape

    nx = (w + sx - 1) // sx
    ny = (h + sy - 1) // sy

    mean_map = np.zeros((ny, nx), dtype=np.float32)
    std_map = np.zeros((ny, nx), dtype=np.float32)

    for j in range(ny):
        y_start = j * sy
        y_end = min((j + 1) * sy, h)

        for i in range(nx):
            x_start = i * sx
            x_end = min((i + 1) * sx, w)

            tile = gray[y_start:y_end, x_start:x_end]
            mean_map[j, i] = np.mean(tile)
            std_map[j, i] = np.std(tile)

    if smoothx > 0 or smoothy > 0:
        sigma_x = smoothx / 2.0
        sigma_y = smoothy / 2.0
        mean_map = gaussian_filter(mean_map, sigma=(sigma_y, sigma_x))
        std_map = gaussian_filter(std_map, sigma=(sigma_y, sigma_x))

    x_coords = (np.arange(nx) + 0.5) * sx
    y_coords = (np.arange(ny) + 0.5) * sy

    mean_interp = RectBivariateSpline(y_coords, x_coords, mean_map, kx=1, ky=1)
    std_interp = RectBivariateSpline(y_coords, x_coords, std_map, kx=1, ky=1)

    x_full = np.arange(w)
    y_full = np.arange(h)
    mean_full = mean_interp(y_full, x_full)
    std_full = std_interp(y_full, x_full)

    std_full = np.maximum(std_full, mindiff)
    normalized = (gray - mean_full) / std_full * target_std + target_mean
    normalized = np.clip(normalized, 0, 255)

    return normalized.astype(np.uint8)


# =============================================================================
# 3. GRAYSCALE NORMALIZATION
# =============================================================================

def pixGrayNormalize(
        image: np.ndarray,
        black_clip: float = 0.0,
        white_clip: float = 0.0
) -> np.ndarray:
    """
    Simple histogram stretching - matches pixGrayNormalize().

    Maps [min_val, max_val] → [0, 255] with optional percentile clipping.

    Args:
        image: Input grayscale image
        black_clip: Fraction to clip from dark end (0.0-0.5)
        white_clip: Fraction to clip from bright end (0.0-0.5)

    Returns:
        Normalized image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    if black_clip > 0 or white_clip > 0:
        # Use percentiles for clipping
        min_val = np.percentile(gray, black_clip * 100)
        max_val = np.percentile(gray, 100 - white_clip * 100)
    else:
        min_val = gray.min()
        max_val = gray.max()

    # Avoid division by zero
    if max_val - min_val < 1:
        return gray.astype(np.uint8)

    # Linear stretch
    normalized = (gray - min_val) / (max_val - min_val) * 255.0
    normalized = np.clip(normalized, 0, 255)

    return normalized.astype(np.uint8)


def pixGrayNormalizeTo(
        image: np.ndarray,
        target_mean: float = 128.0,
        target_std: float = 64.0
) -> np.ndarray:
    """
    Normalize to specific mean and standard deviation.

    Formula: output = (input - current_mean) / current_std * target_std + target_mean

    Args:
        image: Input grayscale image
        target_mean: Desired mean value
        target_std: Desired standard deviation

    Returns:
        Normalized image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    current_mean = np.mean(gray)
    current_std = np.std(gray)

    # Avoid division by zero
    if current_std < 1:
        current_std = 1.0

    # Normalize
    normalized = (gray - current_mean) / current_std * target_std + target_mean
    normalized = np.clip(normalized, 0, 255)

    return normalized.astype(np.uint8)


# =============================================================================
# 4. RANK FILTERING
# =============================================================================

def pixRankFilterGray(
        image: np.ndarray,
        size: int = 5,
        rank: float = 0.5  # 0.0=min, 0.5=median, 1.0=max
) -> np.ndarray:
    """
    Rank filter - matches pixRankFilterGray().

    Args:
        image: Input grayscale image
        size: Filter window size (must be odd)
        rank: Rank value (0.0 to 1.0)
              0.0 = minimum filter
              0.5 = median filter
              1.0 = maximum filter
              0.1 = 10th percentile, etc.

    Returns:
        Filtered image (uint8)
    """
    gray = rgb2gray(image)

    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)

    # Ensure odd size
    if size % 2 == 0:
        size += 1

    # Convert rank to percentile (0-100)
    percentile = int(rank * 100)

    # Use scipy's rank_filter (percentile filter)
    filtered = rank_filter(gray, rank=percentile, size=size)

    return filtered.astype(np.uint8)


def pixMinFilterGray(image: np.ndarray, size: int = 5) -> np.ndarray:
    """Minimum filter (erosion) - convenience wrapper."""
    return pixRankFilterGray(image, size=size, rank=0.0)


def pixMaxFilterGray(image: np.ndarray, size: int = 5) -> np.ndarray:
    """Maximum filter (dilation) - convenience wrapper."""
    return pixRankFilterGray(image, size=size, rank=1.0)


def pixMedianFilterGray(image: np.ndarray, size: int = 5) -> np.ndarray:
    """Median filter - convenience wrapper."""
    return pixRankFilterGray(image, size=size, rank=0.5)


# =============================================================================
# 5. UNSHARP MASKING
# =============================================================================

def pixUnsharpMaskingGray(
        image: np.ndarray,
        halfwidth: int = 5,
        fract: float = 2.5
) -> np.ndarray:
    """
    Unsharp masking - matches pixUnsharpMaskingGray().

    Formula: output = input + fract * (input - blurred)

    Args:
        image: Input grayscale image
        halfwidth: Half-width of Gaussian blur (sigma = halfwidth/2)
        fract: Sharpening amount (1.0-5.0 typical)
               Higher = more sharpening

    Returns:
        Sharpened image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Gaussian blur
    sigma = halfwidth / 2.0
    blurred = gaussian_filter(gray, sigma=sigma)

    # Unsharp mask: original + amount * (original - blurred)
    sharpened = gray + fract * (gray - blurred)
    sharpened = np.clip(sharpened, 0, 255)

    return sharpened.astype(np.uint8)


# =============================================================================
# 6. HISTOGRAM EQUALIZATION
# =============================================================================

def pixEqualizeHistogram(image: np.ndarray) -> np.ndarray:
    """
    Global histogram equalization - matches pixEqualizeHistogram().

    Redistributes intensity values to achieve uniform histogram.

    Args:
        image: Input grayscale image

    Returns:
        Equalized image (uint8)
    """
    gray = rgb2gray(image)

    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)

    # Use OpenCV's histogram equalization (matches Leptonica exactly)
    equalized = cv2.equalizeHist(gray)

    return equalized


# =============================================================================
# 7. COLOR NORMALIZATION
# =============================================================================

def pixLinearMapToTargetColor(
        image: np.ndarray,
        target_mean: tuple = (128, 128, 128),
        target_std: tuple = (64, 64, 64)
) -> np.ndarray:
    """
    Linear color normalization - matches pixLinearMapToTargetColor().

    Normalizes each RGB channel independently to target mean/std.

    Args:
        image: Input color image (RGB)
        target_mean: Target (R, G, B) mean values
        target_std: Target (R, G, B) standard deviations

    Returns:
        Normalized color image (uint8)
    """
    if image.ndim != 3:
        raise ValueError("Input must be color (3-channel) image")

    img = ensure_float32(image)

    # Process each channel
    result = np.zeros_like(img)

    for c in range(3):
        channel = img[:, :, c]

        current_mean = np.mean(channel)
        current_std = np.std(channel)

        if current_std < 1:
            current_std = 1.0

        # Normalize
        normalized = (channel - current_mean) / current_std * target_std[c] + target_mean[c]
        result[:, :, c] = np.clip(normalized, 0, 255)

    return result.astype(np.uint8)


# =============================================================================
# DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    import matplotlib.pyplot as plt

    # Load your image
    filename = 'C:/AutoCompanyImages/DOSTPLUS/LHS/2 - Hub and Bottom Bearing - 1.png'
    img = plt.imread(filename)

    # Test different normalizations
    results = {
        'Original': rgb2gray(img),
        'Background Norm': pixBackgroundNorm(img, sx=15, sy=15),
        'Background Simple': pixBackgroundNormSimple(img, size=50),
        'Contrast Norm': pixContrastNorm(img, sx=10, sy=10, mindiff=30),
        'Gray Normalize': pixGrayNormalize(img),
        'Rank Filter (5th %)': pixRankFilterGray(img, size=31, rank=0.05),
        'Unsharp Mask': pixUnsharpMaskingGray(img, halfwidth=5, fract=2.5),
        'Histogram Eq': pixEqualizeHistogram(img)
    }

    # Display
    fig, axs = plt.subplots(3, 3, figsize=(15, 15))
    axs = axs.ravel()

    for idx, (title, result) in enumerate(results.items()):
        axs[idx].imshow(result, cmap='gray')
        axs[idx].set_title(title)
        axs[idx].axis('off')

    plt.tight_layout()
    plt.show()

    # =========================================================================
    # Recommended combination for scribble detection on metal:
    # =========================================================================
    print("\n=== Recommended Pipeline for Metal Scribble Detection ===")

    # Step 1: Remove background lighting
    step1 = pixBackgroundNorm(img, sx=20, sy=20, bgval=200)

    # Step 2: Enhance local contrast
    step2 = pixContrastNorm(step1, sx=8, sy=8, mindiff=20)

    # Step 3: Sharpen edges
    step3 = pixUnsharpMaskingGray(step2, halfwidth=3, fract=2.0)

    # Display pipeline
    fig, axs = plt.subplots(1, 4, figsize=(16, 4))
    axs[0].imshow(rgb2gray(img), cmap='gray')
    axs[0].set_title('Original')
    axs[1].imshow(step1, cmap='gray')
    axs[1].set_title('Step 1: Background Removal')
    axs[2].imshow(step2, cmap='gray')
    axs[2].set_title('Step 2: Contrast Enhancement')
    axs[3].imshow(step3, cmap='gray')
    axs[3].set_title('Step 3: Sharpening')

    for ax in axs:
        ax.axis('off')

    plt.tight_layout()
    plt.show()