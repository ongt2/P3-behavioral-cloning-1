import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.misc
import random
import os
from scipy.ndimage import rotate
from scipy.stats import bernoulli

# Some useful constants
DATA_PATH='./udacity'
DRIVING_LOG_FILE = DATA_PATH + '/driving_log.csv'
COLUMNS = ['center','left','right','steering','throttle','brake','speed']

print("Log File:", DRIVING_LOG_FILE)

offset=1.0
dist=10.0
STEERING_COEFFICIENT = offset/dist * 360/( 2*np.pi)  / 25.0
resize_dim=(64,64)
print("Steering coeff=",STEERING_COEFFICIENT)

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

# Generate a random triangular shade on the image
# area parameter is a percentage of the total image area
def random_shades(image, area=0.1):
    # Generate a separate buffer
    shadows = image.copy()

    image_area = shadows.shape[0] * shadows.shape[1]
    # print("Area: %f" % image_area)
    shadow_area = area * image_area
    # print("Shadow area: %f" % shadow_area)
    poly = get_triangle(shadow_area, shadows.shape[0], shadows.shape[1])
    # print(poly)
    cv2.fillPoly(shadows, np.array([poly]), -1)

    alpha = .6
    return cv2.addWeighted(shadows, alpha, image, 1-alpha,0,image)

def get_triangle(area, max_x, max_y):
    # choose
    # print("Triangle max_x: %d max_y: %d, area %f" % (max_x, max_y,area) )
    # Get a random point within the constraints
    x1 = random.randint(0, max_x)
    y1 = random.randint(0, max_y)
    # Get some other random point within the constraints,
    x2 = random.randint(0, max_x)
    y2 = random.randint(0, max_y)
    # Get some other point, making sure the area now 
    n = 2 * area - x1 * y2 + x2 * y1
    m = y1 - x1
    p = x2 - y2
    # print("n = %f, m = %f, p = %f"% (n,m,p))
    max_y3 = int(n/m) if m != 0 else int(n)
    y3 = random.randint(0, abs(max_y3))
    # print("y3 = %f"% y3)
    max_x3 = int(n/p - m * y3) if p != 0 else int(n)
    x3 = random.randint(0, abs(max_x3))
    return [[x1,y1],[x2,y2],[x3,y3]]

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

def random_crop(image,steering=0.0,tx_lower=-20,tx_upper=20,ty_lower=-2,ty_upper=2,rand=True):
    # we will randomly crop subsections of the image and use them as our data set.
    # also the input to the network will need to be cropped, but of course not randomly and centered.
    shape = image.shape
    col_start,col_end =abs(tx_lower),shape[1]-tx_upper
    horizon=60;
    bonnet=136
    if rand:
        tx= np.random.randint(tx_lower,tx_upper+1)
        ty= np.random.randint(ty_lower,ty_upper+1)
    else:
        tx,ty=0,0
    
    #    print('tx = ',tx,'ty = ',ty)
    random_crop = image[horizon+ty:bonnet+ty,col_start+tx:col_end+tx,:]
    image = cv2.resize(random_crop,resize_dim,cv2.INTER_AREA)
    # the steering variable needs to be updated to counteract the shift 
    if tx_lower != tx_upper:
        dsteering = -tx/(tx_upper-tx_lower)/3.0
    else:
        dsteering = 0
    steering += dsteering
    
    return image,steering

def random_brightness(image):
    image1 = cv2.cvtColor(image,cv2.COLOR_RGB2HSV)
    random_bright = 0.8 + 0.4*(2*np.random.uniform()-1.0)    
    image1[:,:,2] = image1[:,:,2]*random_bright
    image1 = cv2.cvtColor(image1,cv2.COLOR_HSV2RGB)
    return image1

def generate_new_image(image, steering_angle, do_shear_prob=0.9):
    """
    :param image:
    :param steering_angle:
    :param do_shear_prob:
    :param shear_range:
    :return:
    """

    image = random_shades(image)
    head = bernoulli.rvs(do_shear_prob)
    if head == 1:
        image, steering_angle = random_shear(image, steering_angle)

    image, steering_angle = random_crop(image, steering_angle,tx_lower=-20,tx_upper=20,ty_lower=-10,ty_upper=10, rand=True)

    image, steering_angle = random_flip(image, steering_angle)

    image = random_brightness(image)

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
    if rnd == COLUMNS.index('left'):
        angle = angle + STEERING_COEFFICIENT
    elif rnd == COLUMNS.index('right'):
        angle = angle - STEERING_COEFFICIENT

    return (img, angle)

def next_batch(csv, batch_size=64):
    # Get a random batch of data rows
    random_rows = np.random.randint(0, len(csv), batch_size)
    
    batch = []
    for index in random_rows:
        data = get_random_camera_data(csv, index)
        batch.append(data)

    return batch

def generate_next_batch(batch_size=64):
    csv = pd.read_csv(DRIVING_LOG_FILE)

    while True:
        X_batch = []
        y_batch = []
        images = next_batch(csv, batch_size)
        for img_file, angle in images:
            raw_image = plt.imread(img_file)
            raw_angle = angle
            new_image, new_angle = generate_new_image(raw_image, raw_angle)
            X_batch.append(new_image)
            y_batch.append(new_angle)

        yield np.array(X_batch), np.array(y_batch)
