import cv2 as cv
import svgwrite
import numpy as np
import os
from typing import Tuple


def resize_image(image: np.ndarray, max_width: int, max_height: int) -> np.ndarray:
    """
    Resizes an image while maintaining its aspect ratio to fit within a given size.

    Args:
        image (np.ndarray): The image to be resized.
        max_width (int): The maximum width of the resized image.
        max_height (int): The maximum height of the resized image.

    Returns:
        np.ndarray: The resized image.
    """
    height, width = image.shape[:2]
    aspect_ratio = width / height

    if width > max_width or height > max_height:
        if width > height:
            new_width = max_width
            new_height = int(max_width / aspect_ratio)
        else:
            new_height = max_height
            new_width = int(max_height * aspect_ratio)
        return cv.resize(image, (new_width, new_height), interpolation=cv.INTER_AREA)
    return image


def get_user_dimensions() -> Tuple[float, float]:
    """
    Prompts the user for the dimensions of the SVG in inches.

    Returns:
        Tuple[float, float]: Height and width in millimeters.
    """
    svg_height_in = float(input("Enter height in inches: "))
    svg_width_in = float(input("Enter width in inches: "))
    svg_height_mm = svg_height_in * 25.4
    svg_width_mm = svg_width_in * 25.4
    return svg_height_mm, svg_width_mm


def process_image(image_filename: str, svg_height_mm: float, svg_width_mm: float) -> None:
    """
    Processes the image using a complex workflow including blurring and morphological operations with additional
    control sliders for various parameters, including line thickness.
    """
    # Load the input image
    image = cv.imread(image_filename)
    if image is None:
        print(f"Error: Unable to open the image file '{image_filename}'. Please check the filename and try again.")
        return

    # Resize the image while maintaining the aspect ratio
    image_resized = resize_image(image, max_width=600, max_height=400)

    # Convert to grayscale
    image_grayscale = cv.cvtColor(image_resized, cv.COLOR_BGR2GRAY)

    # Initialize the window with trackbars
    win_name = 'Edge Detection'
    cv.namedWindow(win_name, cv.WINDOW_NORMAL)
    cv.resizeWindow(win_name, min(image_resized.shape[1], 600), min(image_resized.shape[0], 400))

    # Trackbars for various parameters
    cv.createTrackbar('minThresh', win_name, 30, 255, lambda x: None)  # Canny Min Threshold
    cv.createTrackbar('maxThresh', win_name, 100, 255, lambda x: None)  # Canny Max Threshold
    cv.createTrackbar('Line Thickness', win_name, 1, 10, lambda x: None)  # Line Thickness Slider

    # Trackbars for Gaussian Blur parameters
    cv.createTrackbar('Gaussian Kernel', win_name, 5, 50, lambda x: None)  # Must be odd for Gaussian Blur

    # Set a fixed default kernel for dilation
    dilation_iter = 1  # Fixed iteration count

    while True:
        # Get trackbar values
        minThresh = cv.getTrackbarPos('minThresh', win_name)
        maxThresh = cv.getTrackbarPos('maxThresh', win_name)

        # Gaussian blur kernel size (ensure it's odd and at least 1)
        gaussian_kernel = cv.getTrackbarPos('Gaussian Kernel', win_name)
        if gaussian_kernel % 2 == 0:
            gaussian_kernel += 1
        if gaussian_kernel < 1:
            gaussian_kernel = 1

        # Line thickness from trackbar (scaling it to a reasonable range for kernel size)
        line_thickness = cv.getTrackbarPos('Line Thickness', win_name) + 1  # Min 1, max 10
        thickness_kernel = cv.getStructuringElement(cv.MORPH_RECT, (line_thickness, line_thickness))

        # Apply Gaussian blurring
        blurred_image = cv.GaussianBlur(image_grayscale, (gaussian_kernel, gaussian_kernel), 0)

        # Apply Canny edge detection with current thresholds
        cannyEdge = cv.Canny(blurred_image, minThresh, maxThresh)

        # Apply dilation with the default kernel for line thickness adjustment
        refinedEdge = cv.dilate(cannyEdge, thickness_kernel, iterations=dilation_iter)

        # Create a black background for stamp (inverted)
        stencil_canvas = np.ones_like(image_grayscale) * 0  # Black background
        stencil_canvas[refinedEdge == 0] = 255  # White edges for stamp

        # Display the preview
        cv.imshow(win_name, stencil_canvas)

        # Check for window closure or pressing 'Esc' (ASCII 27)
        key = cv.waitKey(1)
        if key == 27 or cv.getWindowProperty(win_name, cv.WND_PROP_VISIBLE) < 1:
            # Save the SVG file before exiting
            save_svg('rubber_stamp.svg', svg_width_mm, svg_height_mm, stencil_canvas)
            break

    cv.destroyAllWindows()


def save_svg(filename: str, width_mm: float, height_mm: float, stencil_canvas: np.ndarray) -> None:
    """
    Saves the given stencil canvas as an SVG file with the background filled and edges untouched,
    and adds a thin red border for laser cutting.

    Args:
        filename (str): The output SVG filename.
        width_mm (float): The width of the SVG in millimeters.
        height_mm (float): The height of the SVG in millimeters.
        stencil_canvas (np.ndarray): The stencil image to save.
    """
    dwg = svgwrite.Drawing(filename, size=(f"{width_mm}mm", f"{height_mm}mm"),
                           viewBox=f"0 0 {stencil_canvas.shape[1]} {stencil_canvas.shape[0]}")

    # Add the filled background to be engraved
    dwg.add(dwg.rect(insert=(0, 0), size=(stencil_canvas.shape[1], stencil_canvas.shape[0]),
                     fill='black'))

    # Create a path to represent the edges that should be raised (not engraved)
    edge_path = dwg.path(fill='none', stroke='white', stroke_width=1)

    # Iterate through stencil_canvas and add paths for the edges
    for y in range(stencil_canvas.shape[0]):
        for x in range(stencil_canvas.shape[1]):
            if stencil_canvas[y, x] == 0:  # Black edges in stencil_canvas
                edge_path.push(f'M {x},{y} h 1 v 1 h -1 z')

    dwg.add(edge_path)

    # Add a thin red border for laser cutting
    border_thickness_pt = 0.072  # Border thickness in points (pt)
    # Convert points to mm (1 pt = 0.35278 mm)
    border_thickness_mm = border_thickness_pt * 0.35278
    dwg.add(dwg.rect(insert=(0, 0), size=(stencil_canvas.shape[1], stencil_canvas.shape[0]),
                     fill='none', stroke='red', stroke_width=border_thickness_mm))

    # Save the SVG file
    dwg.save()
    print(f"SVG saved as '{filename}'")


if __name__ == "__main__":
    # Main script to execute the appropriate function based on user input
    image_filename = input("Enter the image path (e.g., 'images/image.jpg'): ")

    if not os.path.isfile(image_filename):
        print(f"Error: Unable to find the image file '{image_filename}'. Please check the path and extension and try again.")
    else:
        svg_height_mm, svg_width_mm = get_user_dimensions()
        process_image(image_filename, svg_height_mm, svg_width_mm)