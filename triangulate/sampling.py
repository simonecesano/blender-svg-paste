import numpy as np
import math
import random
from shapely import Point, Polygon
from random import randrange
from sklearn.cluster import KMeans
from scipy.stats import qmc

def blue_noise_sampling(polygon, count, k=30):
    xmin, ymin, xmax, ymax = polygon.bounds

    area = (xmax - xmin) * (ymax - ymin)
    density = count / polygon.area 
    radius = np.sqrt(2 / (3 * np.sqrt(3) * density))

    cell_size = radius / np.sqrt(2)
    grid_width = int((xmax - xmin) / cell_size) + 1
    grid_height = int((ymax - ymin) / cell_size) + 1
    grid = [[-1 for _ in range(grid_height)] for _ in range(grid_width)]
    samples = []
    process_list = []

    def grid_coords(point): return int((point[0] - xmin) / cell_size), int((point[1] - ymin) / cell_size)
    def in_bounds(point): return polygon.contains(Point(point[0], point[1]))

    def fits(point):
        gx, gy = grid_coords(point)
        for i in range(max(0, gx-2), min(gx+3, grid_width)):
            for j in range(max(0, gy-2), min(gy+3, grid_height)):
                if grid[i][j] != -1:
                    distance = np.linalg.norm(np.array(point) - np.array(samples[grid[i][j]]))
                    if distance < radius:
                        return False
        return True

    def add_point(point):
        samples.append(point)
        process_list.append(point)
        gx, gy = grid_coords(point)
        grid[gx][gy] = len(samples) - 1

    first_point = (random.uniform(xmin, xmax), random.uniform(ymin, ymax))
    while not in_bounds(first_point): first_point = (random.uniform(xmin, xmax), random.uniform(ymin, ymax))
    add_point(first_point)

    while process_list:
        point = process_list.pop(random.randint(0, len(process_list) - 1))
        for _ in range(k):
            angle = random.uniform(0, 2 * np.pi)
            r = random.uniform(radius, 2 * radius)
            new_point = (point[0] + r * np.cos(angle), point[1] + r * np.sin(angle))
            if in_bounds(new_point) and fits(new_point):
                add_point(new_point)

    return samples


def random_points_sampling(poly, count):
    xmin, ymin, xmax, ymax = poly.bounds
    bbox = poly.bounds
    w = xmax - xmin
    h = ymax - ymin
    
    l = xmin
    t = ymin
    
    points = []
    
    i = 0
    ti = 1000000000 # because random wants integers

    while i < count:
        p = Point(randrange(math.floor(l * ti), math.ceil(w + l) * ti) / ti, randrange(math.floor(t * ti), math.ceil((h + t) * ti)) / ti)
        if(poly.contains(p)):
            points.append(p)
            i = i + 1
    return points

def uniform_grid_sampling(polygon, num_points):
    area = polygon.area
    desired_density = num_points / area
    spacing = np.sqrt(1 / desired_density)    

    xmin, ymin, xmax, ymax = polygon.bounds
    x_coords = np.arange(xmin, xmax, spacing)
    y_coords = np.arange(ymin, ymax, spacing)
    envelope = polygon.envelope
    grid_points = np.array([(x, y) for x in x_coords for y in y_coords if polygon.contains(Point(x, y))])
    return grid_points.tolist()


def hexagonal_grid_sampling(polygon, count):
    xmin, ymin, xmax, ymax = polygon.bounds
    area = (xmax - xmin) * (ymax - ymin)
    # ratio = area / polygon.area
    density = count / polygon.area 
    radius = np.sqrt(2 / (3 * np.sqrt(3) * density))
    
    width = radius * 2
    height = np.sqrt(3) * radius
    hex_points = []

    for y in np.arange(ymin, ymax + height, height):
        for x in np.arange(xmin, xmax + width, width):
            if polygon.contains(Point(x, y)):
                hex_points.append((x, y))
            if polygon.contains(Point(x + radius, y + height / 2)):
                hex_points.append((x + radius, y + height / 2))
    
    return hex_points

def centroid_sampling(poly, count):
    # https://github.com/dpasut/python_cvt/blob/master/cvt.py
    xmin, ymin, xmax, ymax = poly.bounds
    area = (xmax - xmin) * (ymax - ymin)
    
    random_seed = None
    num_centroids = int(count * area / poly.area)
    dimensionality = 2
    num_samples = 10 * num_centroids
    num_replicates = 1
    max_iterations = 100
    tolerance = 0.0001
    verbose = 0
    algorithm = "lloyd"
    X = np.random.rand(num_samples, dimensionality)

    kmeans = KMeans(
        init="k-means++",
        algorithm=algorithm,
        n_clusters=num_centroids,
        n_init=num_replicates,
        max_iter=max_iterations,
        tol=tolerance,
        verbose=verbose,
    )

    kmeans.fit(X)
    centroids = kmeans.cluster_centers_
    
    width = xmax - xmin
    height = ymax - ymin

    scale_factor = max(width, height)
    centroids[:, :2] *= scale_factor
    centroids[:, 0] += xmin
    centroids[:, 1] += ymin
    points = []

    for c in centroids.tolist():
        if poly.contains(Point(c[0], c[1])):
            points.append(c)
    return points

def poisson_disc_sampling(polygon, num_points):
    # Get the bounding box from the polygon
    minx, miny, maxx, maxy = polygon.bounds

    bounds = np.array([[minx, maxx], [miny, maxy]])

    # Calculate radius for Poisson disc sampling
    area = polygon.area
    radius = np.sqrt(area / (num_points * np.pi))

    # Create Poisson disc sampler
    sampler = qmc.PoissonDisk(d=2, radius=radius)

    # Generate points
    sample = sampler.fill_space()

    # Scale the points to fit the bounding box
    sample = qmc.scale(sample, bounds[:, 0], bounds[:, 1])

    # Filter points to keep only those inside the polygon
    points = [tuple(point) for point in sample if polygon.contains(Point(point))]

    # Ensure we have the desired number of points
    while len(points) < num_points:
        extra_sample = sampler.fill_space()
        extra_sample = qmc.scale(extra_sample, bounds[:, 0], bounds[:, 1])
        points += [tuple(point) for point in extra_sample if polygon.contains(Point(point))]
        points = points[:num_points]
        
    return points
