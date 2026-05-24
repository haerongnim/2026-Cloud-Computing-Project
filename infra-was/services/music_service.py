PLAYLISTS = {
    "HAPPY": [
        "Pharrell Williams - Happy",
        "Justin Timberlake - Can't Stop The Feeling",
    ],
    "SAD": ["Adele - Someone Like You", "Elliott Smith - Between the Bars"],
    "CALM": ["Lauv - Paris in the Rain", "Taylor Swift - Fate of Ophelia"],
    "ANGRY": ["Linkin Park - Numb", "Imagine Dragons - Believer"],
}


def recommend_music(emotion: str):

    return PLAYLISTS.get(emotion, [])
