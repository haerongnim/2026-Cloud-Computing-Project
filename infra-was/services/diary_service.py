from repositories.diary_repository import save_diary


def create_diary(email: str, emotion_result: dict, playlist: list, image_filename: str):

    return save_diary(
        email=email,
        emotion_result=emotion_result,
        playlist=playlist,
        image_filename=image_filename,
    )
