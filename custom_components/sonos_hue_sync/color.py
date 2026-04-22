
import requests, numpy as np
from PIL import Image
from io import BytesIO
from sklearn.cluster import KMeans

def extract_colors(url):
    img = Image.open(BytesIO(requests.get(url, timeout=5).content))
    img = img.convert("RGB")
    img.thumbnail((150,150))
    pixels = np.array(img).reshape(-1,3)
    kmeans = KMeans(n_clusters=3, n_init=10).fit(pixels)
    return [tuple(map(int,c)) for c in kmeans.cluster_centers_]
