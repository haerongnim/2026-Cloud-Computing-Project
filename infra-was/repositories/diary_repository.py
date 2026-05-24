from datetime import datetime


def save_diary(email: str, emotion_result: dict, playlist: list, image_filename: str):

    diary_item = {
        "email": email,
        "emotion": emotion_result["emotion"],
        "confidence": emotion_result["confidence"],
        "playlist": playlist,
        "image_filename": image_filename,
        "created_at": datetime.utcnow().isoformat(),
    }

    print("\n=== MOCK DYNAMODB SAVE ===")
    print(diary_item)
    print("==========================\n")

    return diary_item
