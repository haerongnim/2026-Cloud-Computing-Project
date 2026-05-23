import random

EMOTIONS = ["HAPPY", "SAD", "CALM", "ANGRY"]


def analyze_emotion(image_path: str):

    emotion = random.choice(EMOTIONS)

    return {"emotion": emotion, "confidence": round(random.uniform(80, 99), 2)}
