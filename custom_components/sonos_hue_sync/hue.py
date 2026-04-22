
import requests

class HueBridgeManager:
    def __init__(self, ip, key):
        self.ip = ip
        self.key = key

    def get_groups(self):
        return requests.get(f"http://{self.ip}/api/{self.key}/groups", timeout=5).json()

    def set_light_color(self, light, rgb):
        r,g,b=[x/255 for x in rgb]
        x=r*0.664511+g*0.154324+b*0.162028
        y=r*0.283881+g*0.668433+b*0.047685
        xy=[x/(x+y),y/(x+y)] if x+y else [0.3,0.3]
        requests.put(f"http://{self.ip}/api/{self.key}/lights/{light}/state",
            json={"xy":xy,"bri":int(max(r,g,b)*254)},timeout=5)
