import cv2
import matplotlib.pyplot as plt
import scipy.misc
from scipy.ndimage import rotate
from scipy.stats import bernoulli
from PIL import Image
import os
import numpy as np
import pandas as pd

# Some useful constants
DRIVING_LOG_FILE = 'driving_log.csv'
# Taken from https://github.com/upul/behavioral_cloning
STEERING_COEFFICIENT = 0.229
COLUMNS = ['center','left','right','steering','throttle','brake','speed']

def crop(image, top_percent, bottom_percent):
    """
    Crops an image according to the given parameters
    :param image: source image
    :param top_percent:
        The percentage of the original image will be cropped from the top of the image
    :param bottom_percent:
        The percentage of the original image will be cropped from the bottom of the image
    :return:
        The cropped image
    """
    assert 0 <= top_percent < 0.5, 'top_percent should be between 0.0 and 0.5'
    assert 0 <= bottom_percent < 0.5, 'top_percent should be between 0.0 and 0.5'

    top = int(np.ceil(image.shape[0] * top_percent))
    bottom = image.shape[0] - int(np.ceil(image.shape[0] * bottom_percent))

    return image[top:bottom, :]


def resize(image, new_dim):
    """
    Resize a given image according the the new dimension
    :param image:
        Source image
    :param new_dim:
        A tuple which represents the resize dimension
    :return:
        Resize image
    """
    return scipy.misc.imresize(image, new_dim)


def random_flip(image, steering_angle, flipping_prob=0.5):
    """
    Based on the outcome of an coin flip, the image will be flipped.
    If flipping is applied, the steering angle will be negated.
    :param image: Source image
    :param steering_angle: Original steering angle
    :return: Both flipped image and new steering angle
    """
    head = bernoulli.rvs(flipping_prob)
    if head:
        return np.fliplr(image), -1 * steering_angle
    else:
        return image, steering_angle


def random_gamma(image):
    """
    Random gamma correction is used as an alternative method changing the brightness of
    training images.
    http://www.pyimagesearch.com/2015/10/05/opencv-gamma-correction/
    :param image:
        Source image
    :return:
        New image generated by applying gamma correction to the source image
    """
    gamma = np.random.uniform(0.4, 1.5)
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255
                      for i in np.arange(0, 256)]).astype("uint8")

    # apply gamma correction using the lookup table
    return cv2.LUT(image, table)


def random_shear(image, steering_angle, shear_range=200):
    """
    Source: https://medium.com/@ksakmann/behavioral-cloning-make-a-car-drive-like-yourself-dc6021152713#.7k8vfppvk
    :param image:
        Source image on which the shear operation will be applied
    :param steering_angle:
        The steering angle of the image
    :param shear_range:
        Random shear between [-shear_range, shear_range + 1] will be applied
    :return:
        The image generated by applying random shear on the source image
    """
    rows, cols, ch = image.shape
    dx = np.random.randint(-shear_range, shear_range + 1)
    random_point = [cols / 2 + dx, rows / 2]
    pts1 = np.float32([[0, rows], [cols, rows], [cols / 2, rows / 2]])
    pts2 = np.float32([[0, rows], [cols, rows], random_point])
    dsteering = dx / (rows / 2) * 360 / (2 * np.pi * 25.0) / 6.0
    M = cv2.getAffineTransform(pts1, pts2)
    image = cv2.warpAffine(image, M, (cols, rows), borderMode=1)
    steering_angle += dsteering

    return image, steering_angle


def generate_new_image(image, steering_angle, top_crop_percent=0.35, bottom_crop_percent=0.1,
                       resize_dim=(64, 64), do_shear_prob=0.9):
    """
    :param image:
    :param steering_angle:
    :param top_crop_percent:
    :param bottom_crop_percent:
    :param resize_dim:
    :param do_shear_prob:
    :param shear_range:
    :return:
    """
    head = bernoulli.rvs(do_shear_prob)
    if head == 1:
        image, steering_angle = random_shear(image, steering_angle)

    image = crop(image, top_crop_percent, bottom_crop_percent)

    image, steering_angle = random_flip(image, steering_angle)

    image = random_gamma(image)

    image = resize(image, resize_dim)

    return image, steering_angle


# center,left,right,steering,throttle,brake,speed
def get_random_camera_data(csv, index):
    """Get one of the left, center or right images together with
    the corresponding(adjusted) steering angle.
    """
    rnd = np.random.randint(0, 3)
    img = csv.iloc[index][COLUMNS.index('center') + rnd].strip()
    angle = csv.iloc[index][COLUMNS.index('steering')]
    
    # Adjust steering based on camera position
    if COLUMNS.index('center') + rnd == COLUMNS.index('left'):
        angle = angle + STEERING_COEFFICIENT
    elif rnd == COLUMNS.index('right'):
        angle = angle - STEERING_COEFFICIENT

    return (img, angle)


def next_batch(base_dir, batch_size=64):
    log_file = os.path.join(base_dir, DRIVING_LOG_FILE)
    csv = pd.read_csv(log_file)
    # Get a random batch of data rows
    random_rows = np.random.randint(0, len(csv), batch_size)
    
    batch = []
    for index in random_rows:
        data = get_random_camera_data(csv, index)
        batch.append(data)

    return batch

def data_generator(base_dir, batch_size=64):
    while True:
        X_batch = []
        y_batch = []
        images = next_batch(base_dir, batch_size)
        for img_file, angle in images:
            img_file = os.path.join(base_dir, img_file)
            raw_image = plt.imread(img_file)
            raw_angle = angle
            augmented_image, augmented_angle = generate_new_image(raw_image, raw_angle)

            X_batch.append(np.array(augmented_image))
            y_batch.append(augmented_angle)


        assert len(X_batch) == batch_size, 'len(X_batch) == batch_size should be True'

        yield np.array(X_batch), np.array(y_batch)
