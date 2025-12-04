import os
from PIL import Image
def picture_handler(image_file, path):
    filename = image_file.filename
    output_path = os.path.join(path, filename)
    image_file.save(output_path)
    return None
