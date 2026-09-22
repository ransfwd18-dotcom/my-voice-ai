from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import edge_tts
import os
import uuid
import re
from master_director import MasterNarrationDirector

app = FastAPI(title="My Voice AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


class GenerateRequest(BaseModel):
    text: str
    voice: str = "en-US-AriaNeural"
    style: str = "normal"
    emotion: str = "neutral"
    speed: str = "0"
    pitch: str = "0"
    volume: str = "0"


def apply_name_pronunciations(text: str, rules: dict) -> str:
    """
    Applies user-defined name pronunciation rules before TTS.
    The visible text remains unchanged in the interface.
    """

    import re

    if not isinstance(rules, dict):
        return text

    for name, pronunciation in rules.items():

        if not str(name).strip() or not str(pronunciation).strip():
            continue

        pattern = rf"(?<!\w){re.escape(str(name))}(?!\w)"

        text = re.sub(
            pattern,
            str(pronunciation),
            text,
            flags=re.IGNORECASE,
        )

    return text


def number_value(value: str) -> int:
    try:
        number = int(float(value))
    except (ValueError, TypeError):
        number = 0

    return max(-50, min(50, number))


def edge_rate(value: str) -> str:
    number = number_value(value)

    if number >= 0:
        return f"+{number}%"

    return f"{number}%"


def edge_pitch(value: str) -> str:
    number = number_value(value)

    if number >= 0:
        return f"+{number}Hz"

    return f"{number}Hz"


def edge_volume(value: str) -> str:
    number = number_value(value)

    if number >= 0:
        return f"+{number}%"

    return f"{number}%"


# ==========================================
# NATURAL PAUSE ENGINE
# ==========================================





# CUSTOM PRONUNCIATION RULES
# Format:
# "word": "how the TTS should say it"
#
# Add your own words here whenever a name, place, acronym,
# or difficult word is pronounced incorrectly.
CUSTOM_PRONUNCIATION = {
    "OpenAI": "Open A I",
    "ChatGPT": "Chat G P T",
    "YouTube": "You Tube",
    "AI": "A I",
    "TTS": "T T S",
}



# NAME PRONUNCIATION RULES
# Add names here using:
# "Name": "how the TTS should pronounce the name"
#
# These rules are applied before the general pronunciation rules.

NAME_PRONUNCIATION = {
    "Kwame": "Kwa-meh",
    "Kofi": "Ko-fee",
    "Akosua": "Ah-koh-soo-ah",
    "Ama": "Ah-mah",
    "Yaw": "Yaw",
    "Einstein": "Ein-stine",
}


def apply_name_pronunciation(text: str) -> str:
    """
    Applies dedicated pronunciation rules for names.
    """

    import re

    for name, pronunciation in NAME_PRONUNCIATION.items():

        pattern = rf"(?<!\w){re.escape(name)}(?!\w)"

        text = re.sub(
            pattern,
            pronunciation,
            text,
            flags=re.IGNORECASE,
        )

    return text


def apply_custom_pronunciation(text: str) -> str:
    """
    Applies custom pronunciation substitutions before TTS generation.
    The original text shown in the interface is not changed.
    """

    import re

    for original, pronunciation in CUSTOM_PRONUNCIATION.items():

        pattern = rf"(?<!\w){re.escape(original)}(?!\w)"

        text = re.sub(
            pattern,
            pronunciation,
            text,
            flags=re.IGNORECASE,
        )

    return text


def add_sentence_stress(text: str) -> str:
    """
    Adds subtle timing emphasis to the main idea of sentences.
    Preserves the user's actual words.
    """

    import re

    # Common structures where the following phrase carries
    # the main meaning of the sentence.
    patterns = [
        r"\b(the truth is),\s*",
        r"\b(the important thing is),\s*",
        r"\b(the key is),\s*",
        r"\b(what matters is),\s*",
        r"\b(what really matters is),\s*",
        r"\b(the real problem is),\s*",
        r"\b(the main reason is),\s*",
        r"\b(the most important thing is),\s*",
        r"\b(what you need to remember is),\s*",
        r"\b(the answer is),\s*",
        r"\b(here is the point),\s*",
        r"\b(this is why),\s*",
    ]

    for pattern in patterns:
        text = re.sub(
            pattern,
            lambda m: m.group(1) + ", ",
            text,
            flags=re.IGNORECASE,
        )

    # Give contrast structures a clearer timing boundary.
    contrast_patterns = [
        r"\b(not tomorrow),\s*",
        r"\b(not later),\s*",
        r"\b(not someday),\s*",
        r"\b(not because),\s*",
        r"\b(but because),\s*",
        r"\b(but instead),\s*",
    ]

    for pattern in contrast_patterns:
        text = re.sub(
            pattern,
            lambda m: m.group(1) + ", ",
            text,
            flags=re.IGNORECASE,
        )

    # Clean accidental duplicate punctuation.
    text = re.sub(r",\s*,+", ", ", text)
    text = re.sub(r"\s+,", ",", text)

    return text.strip()


def add_word_stress(text: str) -> str:
    """
    Adds subtle punctuation emphasis around contextually important words.
    The original words are preserved.
    """

    import re

    emphasis_words = [
        "important",
        "important!",
        "remember",
        "remember this",
        "never",
        "always",
        "really",
        "truly",
        "especially",
        "finally",
        "however",
        "therefore",
        "the truth is",
        "most importantly",
        "the key",
        "critical",
        "essential",
        "powerful",
    ]

    # Add a small punctuation cue before selected emphasis phrases.
    # Avoid repeatedly modifying text that is already emphasized.
    for phrase in sorted(emphasis_words, key=len, reverse=True):
        pattern = rf"(?<![,â€”])\b({re.escape(phrase)})\b"

        text = re.sub(
            pattern,
            lambda m: ", " + m.group(1),
            text,
            flags=re.IGNORECASE,
        )

    # Clean accidental duplicate commas/spaces.
    text = re.sub(r",\s*,+", ", ", text)
    text = re.sub(r"\s+,", ",", text)

    return text.strip()


def add_micro_pauses(text: str) -> str:
    """
    Adds subtle punctuation timing cues for more natural speech rhythm.
    Does not change the user's words.
    """

    import re

    # Slight pause after common introductory phrases.
    patterns = [
        r"\bWell,\s*",
        r"\bNow,\s*",
        r"\bSo,\s*",
        r"\bLook,\s*",
        r"\bListen,\s*",
        r"\bHonestly,\s*",
        r"\bActually,\s*",
        r"\bBasically,\s*",
        r"\bRemember,\s*",
        r"\bFirst,\s*",
        r"\bSecond,\s*",
        r"\bThird,\s*",
    ]

    for pattern in patterns:
        text = re.sub(
            pattern,
            lambda m: m.group(0).rstrip() + " ",
            text,
            flags=re.IGNORECASE,
        )

    # Slight separation around em dashes.
    text = re.sub(r"\s*[â€”â€“]\s*", " â€” ", text)

    # Keep ellipses as a natural hesitation cue.
    text = re.sub(r"\.{3,}", "...", text)

    # Avoid excessive artificial spacing.
    text = re.sub(r"[ \t]{3,}", "  ", text)

    return text.strip()


def naturalize_text(text: str) -> str:
    """
    Adds subtle punctuation-based timing cues before TTS generation.

    This does not rewrite the user's words.
    It only improves the rhythm and pause structure.
    """

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Normalize excessive spaces while preserving paragraphs.
    text = re.sub(r"[ \t]+", " ", text)

    # Strengthen paragraph separation.
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Give commas a slightly clearer breathing space.
    text = re.sub(r",\s*", ", ", text)

    # Avoid awkward spacing before punctuation.
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)

    # Give semicolons and colons slightly more separation.
    text = re.sub(r";\s*", "; ", text)
    text = re.sub(r":\s*", ": ", text)

    # Make sentence endings clear without changing the words.
    text = re.sub(r"([.!?])\s+", r"\1  ", text)

    # Keep paragraph breaks stronger.
    text = re.sub(r"\n\s*\n", "\n\n", text)

    # Add a subtle pause after common transition phrases.
    transitions = [
        "however",
        "therefore",
        "but",
        "instead",
        "meanwhile",
        "finally",
        "for example",
        "in other words",
        "most importantly",
        "the truth is",
        "remember this",
    ]

    for phrase in transitions:
        pattern = rf"\b({re.escape(phrase)}),?\s+"
        text = re.sub(
            pattern,
            lambda m: m.group(1) + ", ",
            text,
            flags=re.IGNORECASE,
        )

    return text.strip()



# ===== AUTO VOICE INTELLIGENCE =====

def auto_voice_intelligence(text: str, base_speed: str, base_pitch: str, base_volume: str):
    clean = text.strip()
    lower = clean.lower()

    try:
        speed = int(float(base_speed))
    except:
        speed = 0

    try:
        pitch = int(float(base_pitch))
    except:
        pitch = 0

    try:
        volume = int(float(base_volume))
    except:
        volume = 0

    speed = max(-50, min(50, speed))
    pitch = max(-50, min(50, pitch))
    volume = max(-50, min(50, volume))

    if "?" in clean:
        pitch += 2

    excitement_words = [
        "amazing", "incredible", "wow", "excited", "great",
        "fantastic", "wonderful", "awesome", "congratulations",
        "finally"
    ]

    if "!" in clean or any(word in lower for word in excitement_words):
        speed += 4
        pitch += 2
        volume += 2

    serious_words = [
        "danger", "warning", "death", "never forget",
        "important", "critical", "serious", "truth",
        "reality", "mistake", "problem", "consequence",
        "remember this", "the truth is"
    ]

    if any(word in lower for word in serious_words):
        speed -= 4
        pitch -= 1

    calm_words = [
        "peace", "calm", "quiet", "slowly", "breathe",
        "relax", "gentle", "silence", "moment",
        "reflect", "remember"
    ]

    if any(word in lower for word in calm_words):
        speed -= 3
        pitch -= 1

    urgency_words = [
        "now", "urgent", "quickly", "hurry",
        "immediately", "right now", "don't wait",
        "before it's too late"
    ]

    if any(word in lower for word in urgency_words):
        speed += 5
        pitch += 1

    emphasis_phrases = [
        "the truth is",
        "most importantly",
        "remember this",
        "the key is",
        "what matters is",
        "never forget",
        "the important thing is",
        "this is why"
    ]

    for phrase in emphasis_phrases:
        pattern = rf"(?<![,])\b({re.escape(phrase)})\b"
        clean = re.sub(
            pattern,
            lambda m: ", " + m.group(1) + ",",
            clean,
            flags=re.IGNORECASE
        )

    transitions = [
        "however",
        "therefore",
        "but",
        "instead",
        "meanwhile",
        "finally",
        "for example",
        "in other words"
    ]

    for phrase in transitions:
        pattern = rf"(?<![,])\b({re.escape(phrase)})\b"
        clean = re.sub(
            pattern,
            lambda m: ", " + m.group(1) + ",",
            clean,
            flags=re.IGNORECASE
        )

    clean = re.sub(r",\s*,+", ", ", clean)
    clean = re.sub(r"\s+,", ",", clean)
    clean = re.sub(r"[ \t]{2,}", " ", clean)

    speed = max(-50, min(50, speed))
    pitch = max(-50, min(50, pitch))
    volume = max(-50, min(50, volume))

    return clean.strip(), str(speed), str(pitch), str(volume)

# ===== END AUTO VOICE INTELLIGENCE =====


# ===== AUTO EMOTION DETECTION =====

def auto_emotion_detection(text: str):
    import re

    clean = text.strip()
    lower = clean.lower()

    scores = {
        "neutral": 0,
        "happy": 0,
        "sad": 0,
        "angry": 0,
        "excited": 0,
        "calm": 0,
        "serious": 0,
        "urgent": 0,
    }

    word_groups = {
        "happy": [
            "happy", "joy", "joyful", "smile", "laugh", "love",
            "wonderful", "beautiful", "great", "glad", "pleased"
        ],
        "sad": [
            "sad", "sadness", "cry", "tears", "lost", "alone",
            "lonely", "pain", "hurt", "miss", "grief", "sorry"
        ],
        "angry": [
            "angry", "anger", "hate", "furious", "rage", "stupid",
            "terrible", "unacceptable", "enough"
        ],
        "excited": [
            "amazing", "incredible", "awesome", "wow", "fantastic",
            "congratulations", "finally", "excited"
        ],
        "calm": [
            "calm", "peace", "peaceful", "breathe", "relax",
            "quiet", "gentle", "slowly", "silence", "reflect"
        ],
        "serious": [
            "truth", "reality", "important", "critical", "serious",
            "danger", "warning", "mistake", "consequence",
            "remember", "never forget"
        ],
        "urgent": [
            "now", "urgent", "quickly", "hurry", "immediately",
            "right now", "don't wait", "before it's too late"
        ],
    }

    for emotion, words in word_groups.items():
        for word in words:
            if re.search(rf"\b{re.escape(word)}\b", lower):
                scores[emotion] += 1

    if "!" in clean:
        scores["excited"] += 2

    if "?" in clean:
        scores["serious"] += 1

    if "..." in clean:
        scores["sad"] += 1
        scores["calm"] += 1

    emotion = max(scores, key=scores.get)

    if scores[emotion] == 0:
        emotion = "neutral"

    intensity = min(100, max(0, scores[emotion] * 20))

    if clean.count("!") >= 2:
        intensity += 20

    intensity = min(100, intensity)

    return emotion, intensity

# ===== END AUTO EMOTION DETECTION =====

@app.get("/")
async def root():
    return {
        "message": "My Voice AI backend is running"
    }


 # ===== CONFIDENCE ENGINE =====

def detect_confidence(text: str):
    clean = text.strip()
    lower = clean.lower()

    high_words = [
        "definitely", "certainly", "absolutely", "clearly",
        "confident", "strong", "will", "must", "success",
        "win", "victory", "believe", "know", "ready"
    ]

    low_words = [
        "maybe", "perhaps", "possibly", "might", "unsure",
        "uncertain", "afraid", "worried", "sorry", "hopefully",
        "i think", "i guess", "not sure"
    ]

    score = 0

    for word in high_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            score += 2

    for word in low_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            score -= 2

    if "!" in clean:
        score += 1

    if "?" in clean:
        score -= 1

    if score >= 3:
        confidence = "high"
    elif score <= -2:
        confidence = "low"
    else:
        confidence = "normal"

    intensity = min(100, max(20, abs(score) * 20 + 20))

    return confidence, intensity


def confidence_adjustments(confidence: str, intensity: int):
    adjustments = {
        "low":    (-3, -2, -1),
        "normal": (0, 0, 0),
        "high":   (3, 2, 2),
    }

    speed, pitch, volume = adjustments.get(
        confidence,
        (0, 0, 0)
    )

    factor = intensity / 100

    return (
        speed * factor,
        pitch * factor,
        volume * factor
    )

# ===== END CONFIDENCE ENGINE =====
# ===== MOOD ENGINE =====

def detect_mood(text: str):
    clean = text.strip().lower()

    mood_scores = {
        "neutral": 0,
        "peaceful": 0,
        "dark": 0,
        "hopeful": 0,
        "warm": 0,
        "tense": 0,
        "inspiring": 0,
        "reflective": 0,
        "urgent": 0,
    }

    mood_words = {
        "peaceful": ["peace", "peaceful", "quiet", "gentle", "still", "breathe", "calm", "silence", "soft", "rest"],
        "dark": ["dark", "death", "dead", "fear", "night", "shadow", "lost", "alone", "pain", "despair"],
        "hopeful": ["hope", "hopeful", "believe", "tomorrow", "better", "chance", "future", "together", "possible"],
        "warm": ["love", "friend", "family", "home", "kind", "smile", "care", "welcome", "thank"],
        "tense": ["danger", "warning", "threat", "risk", "problem", "wrong", "fear", "attack", "conflict"],
        "inspiring": ["achieve", "success", "strong", "dream", "great", "amazing", "incredible", "win", "victory", "believe"],
        "reflective": ["remember", "think", "wonder", "life", "time", "past", "memory", "meaning", "truth", "realize"],
        "urgent": ["now", "urgent", "quickly", "hurry", "immediately", "right now", "don't wait", "before it's too late"],
    }

    for mood, words in mood_words.items():
        for word in words:
            if re.search(rf"\b{re.escape(word)}\b", clean):
                mood_scores[mood] += 1

    if "..." in clean:
        mood_scores["reflective"] += 1
        mood_scores["peaceful"] += 1

    if "!" in clean:
        mood_scores["inspiring"] += 1

    if "?" in clean:
        mood_scores["reflective"] += 1

    mood = max(mood_scores, key=mood_scores.get)

    if mood_scores[mood] == 0:
        mood = "neutral"

    intensity = min(100, mood_scores[mood] * 20)

    return mood, intensity


def mood_adjustments(mood: str, intensity: int):
    adjustments = {
        "neutral":    (0, 0, 0),
        "peaceful":   (-2, -1, -1),
        "dark":       (-3, -2, -1),
        "hopeful":    (1, 1, 1),
        "warm":       (-1, 1, 1),
        "tense":      (3, 2, 2),
        "inspiring":  (3, 2, 2),
        "reflective": (-2, -1, 0),
        "urgent":     (4, 2, 3),
    }

    speed, pitch, volume = adjustments.get(mood, (0, 0, 0))
    factor = intensity / 100

    return (
        speed * factor,
        pitch * factor,
        volume * factor
    )




# ===== ENERGY ENGINE =====

def detect_energy(text: str):
    clean = text.strip()
    lower = clean.lower()

    score = 0

    high_words = [
        "amazing", "incredible", "awesome", "excited", "urgent",
        "hurry", "quickly", "immediately", "win", "victory",
        "wow", "fantastic", "let's go", "come on", "now", "finally"
    ]

    low_words = [
        "quiet", "peaceful", "calm", "gentle", "soft", "rest",
        "breathe", "silence", "slow", "tired", "sad", "alone"
    ]

    for word in high_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            score += 2

    for word in low_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            score -= 1

    score += clean.count("!") * 2
    score -= clean.count("...")

    if score >= 6:
        energy = "high"
    elif score <= -2:
        energy = "low"
    else:
        energy = "medium"

    intensity = min(100, max(20, abs(score) * 15 + 25))
    return energy, intensity


def energy_adjustments(energy: str, intensity: int):
    adjustments = {
        "low":    (-3, -1, -2),
        "medium": (0, 0, 0),
        "high":   (4, 2, 3),
    }

    speed, pitch, volume = adjustments.get(energy, (0, 0, 0))
    factor = intensity / 100

    return (
        speed * factor,
        pitch * factor,
        volume * factor
    )

# ===== END ENERGY ENGINE =====

# ===== EMOTION VARIATION ENGINE =====

def split_emotion_sentences(text: str):
    """
    Split speech into natural sentence-sized chunks while preserving
    punctuation so each sentence can receive its own emotion.
    """
    parts = re.findall(r'[^.!?]+[.!?]+|[^.!?]+$', text, flags=re.S)

    sentences = []
    for part in parts:
        cleaned = part.strip()
        if cleaned:
            sentences.append(cleaned)

    return sentences


def emotion_adjustment_for_sentence(text: str):
    """
    Detect emotion independently for one sentence.
    Returns emotion, intensity, speed_delta, pitch_delta, volume_delta.
    """

    detected_emotion, intensity = auto_emotion_detection(text)

    emotion_adjustments = {
        "neutral":  (0, 0, 0),
        "happy":    (3, 2, 2),
        "sad":      (-4, -3, -2),
        "angry":    (5, 3, 4),
        "excited":  (6, 4, 4),
        "calm":     (-4, -2, -2),
        "serious":  (-4, -2, 0),
        "urgent":   (5, 2, 3),
    }

    speed_delta, pitch_delta, volume_delta = emotion_adjustments.get(
        detected_emotion,
        (0, 0, 0)
    )

    factor = intensity / 100

    return (
        detected_emotion,
        intensity,
        speed_delta * factor,
        pitch_delta * factor,
        volume_delta * factor,
    )


def clamp_emotion_values(speed, pitch, volume):
    speed = max(-50, min(50, int(round(speed))))
    pitch = max(-50, min(50, int(round(pitch))))
    volume = max(-50, min(50, int(round(volume))))
    return speed, pitch, volume


# ===== END EMOTION VARIATION ENGINE =====

# ===== ATTITUDE ENGINE =====

def detect_attitude(text: str):
    clean = text.strip()
    lower = clean.lower()

    scores = {
        "neutral": 0,
        "confident": 0,
        "friendly": 0,
        "serious": 0,
        "sarcastic": 0,
        "caring": 0,
        "authoritative": 0,
        "suspicious": 0,
        "playful": 0
    }

    groups = {
        "confident": ["definitely","certainly","absolutely","clearly","will","must","know","certain","sure","success"],
        "friendly": ["hello","hi","thanks","thank you","welcome","nice","great","glad","good","friend"],
        "serious": ["important","serious","danger","warning","critical","consequence","truth","never forget"],
        "sarcastic": ["yeah right","sure","obviously","of course","great job","brilliant","wow"],
        "caring": ["please","take care","be safe","rest","breathe","don't worry","i understand"],
        "authoritative": ["listen","stop","do this","follow","must","required","now","immediately"],
        "suspicious": ["really","are you sure","how do i know","strange","suspicious","why would you","what happened"],
        "playful": ["haha","lol","funny","joke","kidding","awesome","yay","wow"]
    }

    for attitude, words in groups.items():
        for word in words:
            if re.search(rf"\b{re.escape(word)}\b", lower):
                scores[attitude] += 1

    if "!" in clean:
        scores["confident"] += 1
        scores["playful"] += 1

    if "?" in clean:
        scores["suspicious"] += 1

    if "..." in clean:
        scores["sarcastic"] += 1

    attitude = max(scores, key=scores.get)

    if scores[attitude] == 0:
        attitude = "neutral"

    intensity = min(100, max(20, scores[attitude] * 20 + 20))
    return attitude, intensity


def attitude_adjustments(attitude: str, intensity: int):
    adjustments = {
        "neutral": (0, 0, 0),
        "confident": (2, 2, 1),
        "friendly": (-1, 1, 2),
        "serious": (-3, -1, 0),
        "sarcastic": (-1, 1, 0),
        "caring": (-2, -1, 1),
        "authoritative": (2, 1, 2),
        "suspicious": (-1, 1, -1),
        "playful": (2, 2, 2)
    }

    speed, pitch, volume = adjustments.get(attitude, (0, 0, 0))
    factor = intensity / 100

    return speed * factor, pitch * factor, volume * factor

# ===== END ATTITUDE ENGINE =====

# ===== EXCITEMENT ENGINE =====

def detect_excitement(text: str):
    clean = text.strip()
    lower = clean.lower()
    score = 0

    excitement_words = [
        "amazing", "incredible", "awesome", "fantastic",
        "wonderful", "wow", "finally", "excited",
        "congratulations", "victory", "win", "success",
        "yes", "yeah", "come on", "let's go", "we did it"
    ]

    for word in excitement_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            score += 2

    score += clean.count("!") * 2

    if clean.isupper() and len(clean) > 3:
        score += 2

    if score >= 10:
        level = "very_high"
    elif score >= 6:
        level = "high"
    elif score >= 3:
        level = "medium"
    else:
        level = "low"

    intensity = min(100, max(0, score * 10))
    return level, intensity


def excitement_adjustments(level: str, intensity: int):
    adjustments = {
        "low": (0, 0, 0),
        "medium": (2, 1, 1),
        "high": (5, 3, 3),
        "very_high": (8, 5, 5)
    }

    speed, pitch, volume = adjustments.get(level, (0, 0, 0))
    factor = intensity / 100

    return (
        speed * factor,
        pitch * factor,
        volume * factor
    )

# ===== END EXCITEMENT ENGINE =====

# ===== ANGER / FRUSTRATION ENGINE =====

def detect_anger(text: str):
    clean = text.strip()
    lower = clean.lower()

    score = 0

    anger_words = [
        "angry", "anger", "furious", "rage", "mad",
        "unacceptable", "ridiculous", "stupid", "idiot",
        "enough", "stop", "shut up", "leave me alone",
        "tired of this", "sick of this", "fed up",
        "hate", "worst", "terrible", "disgusting",
        "why did you", "what are you doing"
    ]

    frustration_words = [
        "again", "always", "never", "keep doing",
        "keeps happening", "cannot believe",
        "seriously", "really", "come on",
        "problem", "mistake", "wrong"
    ]

    for word in anger_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            score += 3

    for word in frustration_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            score += 1

    score += clean.count("!") * 2

    if clean.isupper() and len(clean) > 3:
        score += 3

    if "??" in clean:
        score += 2

    if score >= 10:
        level = "very_high"
    elif score >= 6:
        level = "high"
    elif score >= 3:
        level = "medium"
    else:
        level = "low"

    intensity = min(100, max(0, score * 10))

    return level, intensity


def anger_adjustments(level: str, intensity: int):
    adjustments = {
        "low":       (0, 0, 0),
        "medium":    (3, 1, 2),
        "high":      (6, 3, 4),
        "very_high": (9, 5, 6)
    }

    speed, pitch, volume = adjustments.get(level, (0, 0, 0))
    factor = intensity / 100

    return (
        speed * factor,
        pitch * factor,
        volume * factor
    )

# ===== END ANGER / FRUSTRATION ENGINE =====

# ===== HAPPINESS / PLAYFULNESS ENGINE =====

def detect_happiness(text: str):
    clean = text.strip()
    lower = clean.lower()

    score = 0

    happy_words = [
        "happy", "happiness", "joy", "joyful", "smile",
        "laugh", "love", "wonderful", "beautiful", "great",
        "glad", "pleased", "amazing", "awesome", "fantastic",
        "fun", "funny", "hilarious", "haha", "lol",
        "yay", "yeah", "wow", "congratulations",
        "we did it", "finally", "success", "victory"
    ]

    playful_words = [
        "joke", "kidding", "haha", "lol", "funny",
        "silly", "yay", "oops", "wow", "awesome",
        "come on", "let's go", "whoops"
    ]

    for word in happy_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            score += 2

    for word in playful_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            score += 1

    score += clean.count("!") * 2

    if clean.isupper() and len(clean) > 3:
        score += 2

    if score >= 10:
        level = "very_high"
    elif score >= 6:
        level = "high"
    elif score >= 3:
        level = "medium"
    else:
        level = "low"

    intensity = min(100, max(0, score * 10))

    return level, intensity


def happiness_adjustments(level: str, intensity: int):
    adjustments = {
        "low":       (0, 0, 0),
        "medium":    (2, 2, 1),
        "high":      (4, 3, 3),
        "very_high": (6, 4, 4)
    }

    speed, pitch, volume = adjustments.get(level, (0, 0, 0))
    factor = intensity / 100

    return (
        speed * factor,
        pitch * factor,
        volume * factor
    )

# ===== END HAPPINESS / PLAYFULNESS ENGINE =====

# ===== SADNESS / SERIOUSNESS ENGINE =====

def detect_sadness_seriousness(text: str):
    clean = text.strip()
    lower = clean.lower()

    sad_score = 0
    serious_score = 0

    sad_words = [
        "sad", "sadness", "cry", "crying", "tears",
        "lost", "alone", "lonely", "pain", "hurt",
        "grief", "grieving", "miss", "missing",
        "heartbroken", "broken", "sorry", "regret",
        "death", "dead", "despair", "suffering"
    ]

    serious_words = [
        "serious", "important", "danger", "warning",
        "critical", "consequence", "truth", "reality",
        "mistake", "never forget", "remember",
        "responsibility", "risk", "problem", "failure",
        "attention", "careful", "urgent"
    ]

    for word in sad_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            sad_score += 2

    for word in serious_words:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            serious_score += 2

    if "..." in clean:
        sad_score += 2

    if "!" in clean:
        serious_score += 1

    if "?" in clean:
        serious_score += 1

    if sad_score > serious_score and sad_score > 0:
        mode = "sad"
        score = sad_score
    elif serious_score > 0:
        mode = "serious"
        score = serious_score
    else:
        mode = "neutral"
        score = 0

    if score >= 10:
        level = "very_high"
    elif score >= 6:
        level = "high"
    elif score >= 3:
        level = "medium"
    else:
        level = "low"

    intensity = min(100, max(0, score * 10))

    return mode, level, intensity


def sadness_seriousness_adjustments(mode: str, level: str, intensity: int):
    adjustments = {
        "sad": {
            "low":       (-2, -1, -1),
            "medium":    (-4, -2, -2),
            "high":      (-6, -3, -3),
            "very_high": (-8, -4, -4)
        },
        "serious": {
            "low":       (-1, -1, 0),
            "medium":    (-3, -2, 0),
            "high":      (-5, -3, 0),
            "very_high": (-7, -4, 0)
        },
        "neutral": {
            "low":       (0, 0, 0),
            "medium":    (0, 0, 0),
            "high":      (0, 0, 0),
            "very_high": (0, 0, 0)
        }
    }

    speed, pitch, volume = adjustments.get(
        mode,
        adjustments["neutral"]
    ).get(level, (0, 0, 0))

    factor = intensity / 100

    return (
        speed * factor,
        pitch * factor,
        volume * factor
    )

# ===== END SADNESS / SERIOUSNESS ENGINE =====

# ===== CONVERSATIONAL DELIVERY ENGINE =====

def conversational_delivery_adjustments(text: str, index: int):
    clean = text.strip()

    if not clean:
        return 0, 0, 0

    speed_delta = 0
    pitch_delta = 0
    volume_delta = 0

    if index % 3 == 1:
        speed_delta = 1
        pitch_delta = 1
    elif index % 3 == 2:
        speed_delta = -1
        pitch_delta = -1

    if clean.endswith("?"):
        pitch_delta += 2
        speed_delta -= 1
    elif clean.endswith("!"):
        speed_delta += 2
        pitch_delta += 1
    elif clean.endswith("..."):
        speed_delta -= 2
        pitch_delta -= 1

    if len(clean.split()) <= 5:
        speed_delta += 1

    return speed_delta, pitch_delta, volume_delta

# ===== END CONVERSATIONAL DELIVERY ENGINE =====

# ===== NATURAL HESITATION ENGINE =====

def natural_hesitation_pause(text: str, index: int):
    clean = text.strip()
    words = len(clean.split())

    if not clean:
        return 0

    if clean.endswith("..."):
        return 420

    if clean.endswith("?"):
        return 260

    if clean.endswith("!"):
        return 220

    if words >= 22:
        return 180

    if words >= 14:
        return 130

    if index > 0:
        return 90

    return 0

# ===== END NATURAL HESITATION ENGINE =====
# ===== BREATH & PHRASE RHYTHM ENGINE =====

def breath_phrase_pause(text: str, index: int):
    clean = text.strip()
    words = len(clean.split())

    if not clean:
        return 0

    if clean.endswith("..."):
        return 360

    if words >= 28:
        return 180

    if words >= 20:
        return 130

    if index > 0 and words >= 10:
        return 80

    return 0

# ===== END BREATH & PHRASE RHYTHM ENGINE =====

# ===== CONNECTED SPEECH ENGINE =====

def connected_speech_adjustments(text: str):
    clean = text.strip()
    words = clean.split()

    if not clean:
        return 0, 0, 0

    speed_delta = 0
    pitch_delta = 0
    volume_delta = 0

    if len(words) >= 18:
        speed_delta += 2
    elif len(words) >= 10:
        speed_delta += 1

    if clean.endswith("?"):
        pitch_delta += 1
    elif clean.endswith("..."):
        speed_delta -= 1
        pitch_delta -= 1

    return speed_delta, pitch_delta, volume_delta

# ===== END CONNECTED SPEECH ENGINE =====

# ===== WORD REDUCTION ENGINE =====

def word_reduction_adjustments(text: str):
    words = text.strip().lower().split()
    if not words:
        return 0, 0, 0

    function_words = {"a","an","the","and","or","to","for","of","can","could","would","should","but","so","as","at","in","on","with","from"}
    count = sum(1 for word in words if word.strip(".,!?;:") in function_words)

    if count >= 5:
        return 2, -1, 0
    if count >= 3:
        return 1, 0, 0

    return 0, 0, 0

# ===== END WORD REDUCTION ENGINE =====

# ===== NATURAL INTONATION ENGINE =====

def natural_intonation_adjustments(text: str):
    clean = text.strip()
    if not clean:
        return 0

    if clean.endswith("?"):
        return 3

    if clean.endswith("!"):
        return 2

    if clean.endswith("..."):
        return -2

    if clean.endswith(","):
        return 1

    words = clean.split()
    if len(words) >= 18:
        return 1

    return 0

# ===== END NATURAL INTONATION ENGINE =====

# ===== NATURAL LOUDNESS EMPHASIS ENGINE =====

def natural_emphasis_adjustments(text: str):
    clean = text.strip().lower()
    if not clean:
        return 0

    emphasis_words = {"very","really","extremely","never","always","important","amazing","absolutely","definitely","must","critical","urgent","now","today"}
    words = [word.strip(".,!?;:") for word in clean.split()]
    count = sum(1 for word in words if word in emphasis_words)

    if count >= 2:
        return 3
    if count == 1:
        return 2

    return 0

# ===== END NATURAL LOUDNESS EMPHASIS ENGINE =====

# ===== NATURAL EMPHASIS & FOCUS ENGINE =====

def natural_focus_adjustments(text: str):
    clean = text.strip().lower()
    if not clean:
        return 0, 0, 0

    focus_words = {
        "important","must","never","always","really","very","critical",
        "urgent","remember","understand","because","why","how","truth",
        "time","life","change","choice","choose","now","today","purpose",
        "focus","matter","matters","careful","carefully"
    }

    words = [w.strip(".,!?;:") for w in clean.split()]
    count = sum(1 for w in words if w in focus_words)

    if count >= 3:
        return 3, 1, 2
    if count >= 2:
        return 2, 1, 1
    if count == 1:
        return 1, 0, 1

    return 0, 0, 0

# ===== END NATURAL EMPHASIS & FOCUS ENGINE =====
# ===== NATURAL PACING & THOUGHT FLOW ENGINE =====

def natural_pacing_flow_adjustments(text: str, index: int):
    clean = text.strip()
    if not clean:
        return 0
    words = len(clean.split())
    pause = 0
    if words >= 25:
        pause += 55
    elif words >= 18:
        pause += 35
    elif words >= 10:
        pause += 15
    if clean.endswith('?'):
        pause += 20
    elif clean.endswith('!'):
        pause += 10
    elif clean.endswith('...'):
        pause += 45
    if index > 0:
        pause += 10
    return pause

# ===== END NATURAL PACING & THOUGHT FLOW ENGINE =====

# ===== NATURAL VOICE WARMTH & PRESENCE ENGINE =====

def voice_warmth_presence(audio):
    from pydub.effects import normalize, compress_dynamic_range

    if len(audio) == 0:
        return audio

    audio = compress_dynamic_range(
        audio,
        threshold=-22.0,
        ratio=2.0,
        attack=5.0,
        release=80.0
    )

    audio = normalize(audio, headroom=1.2)
    audio = audio.apply_gain(0.4)

    return audio

# ===== END NATURAL VOICE WARMTH & PRESENCE ENGINE =====

# ===== NATURAL SPEECH TIMING ENGINE =====

def natural_speech_timing_adjustments(text: str, index: int):
    clean = text.strip()
    words = len(clean.split())
    if not clean:
        return 0

    pause = 0
    if words >= 20:
        pause += 45
    elif words >= 12:
        pause += 25

    if index > 0:
        pause += 15

    if clean.endswith("..."):
        pause += 100
    elif clean.endswith("?"):
        pause += 55
    elif clean.endswith("!"):
        pause += 35

    return pause

# ===== END NATURAL SPEECH TIMING ENGINE =====

@app.post("/generate")
async def generate(request: GenerateRequest):

    if not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty."
        )

    filename = f"{uuid.uuid4()}.mp3"

    output_path = os.path.join(
        OUTPUT_DIR,
        filename
    )

    # ===== MASTER NARRATION DIRECTOR =====
    director = MasterNarrationDirector()
    # Existing engines will feed recommendations into the Director.
    # Current generation values remain untouched until the final resolution stage.
    # ===== END MASTER NARRATION DIRECTOR =====


    # ===== NATURAL SPEECH PREPARATION =====
    speech_text = apply_name_pronunciation(
        apply_custom_pronunciation(
            add_sentence_stress(
                add_word_stress(
                    add_micro_pauses(
                        naturalize_text(request.text)
                    )
                )
            )
        )
    )

    # ===== AUTO VOICE INTELLIGENCE =====
    speech_text, auto_speed, auto_pitch, auto_volume = auto_voice_intelligence(
        speech_text,
        request.speed,
        request.pitch,
        request.volume
    )

    # ===== MASTER DIRECTOR BASELINE =====
    director.reset()

    director.set_baseline(
        speed=float(auto_speed),
        pitch=float(auto_pitch),
        volume=float(auto_volume),
    )

    # ===== MOOD DETECTION =====
    detected_mood, mood_intensity = detect_mood(speech_text)
    mood_speed, mood_pitch, mood_volume = mood_adjustments(detected_mood, mood_intensity)

    auto_speed = float(auto_speed) + mood_speed
    auto_pitch = float(auto_pitch) + mood_pitch
    auto_volume = float(auto_volume) + mood_volume

    auto_speed, auto_pitch, auto_volume = clamp_emotion_values(
        auto_speed,
        auto_pitch,
        auto_volume
    )

    print(
        f"Mood: {detected_mood} "
        f"(intensity {mood_intensity}%) | "
        f"speed={auto_speed}, pitch={auto_pitch}, volume={auto_volume}"
    )

    # ===== EMOTION VARIATION =====
    
    # ===== ENERGY ENGINE =====
    detected_energy, energy_intensity = detect_energy(speech_text)
    energy_speed, energy_pitch, energy_volume = energy_adjustments(detected_energy, energy_intensity)
    auto_speed = float(auto_speed) + energy_speed
    auto_pitch = float(auto_pitch) + energy_pitch
    auto_volume = float(auto_volume) + energy_volume
    auto_speed, auto_pitch, auto_volume = clamp_emotion_values(auto_speed, auto_pitch, auto_volume)
    print(f"Energy: {detected_energy} (intensity {energy_intensity}%) | speed={auto_speed}, pitch={auto_pitch}, volume={auto_volume}")
    # ===== END ENERGY ENGINE =====
    # ===== CONFIDENCE ENGINE =====
    detected_confidence, confidence_intensity = detect_confidence(speech_text)
    confidence_speed, confidence_pitch, confidence_volume = confidence_adjustments(
        detected_confidence,
        confidence_intensity
    )

    director.add_recommendation(
        "Confidence",
        speed=confidence_speed,
        pitch=confidence_pitch,
        volume=confidence_volume,
        confidence=float(confidence_intensity),
        reason=f"Confidence: {detected_confidence}"
    )

    auto_speed = float(auto_speed) + confidence_speed
    auto_pitch = float(auto_pitch) + confidence_pitch
    auto_volume = float(auto_volume) + confidence_volume

    auto_speed, auto_pitch, auto_volume = clamp_emotion_values(
        auto_speed,
        auto_pitch,
        auto_volume
    )

    print(
        f"Confidence: {detected_confidence} "
        f"(intensity {confidence_intensity}%) | "
        f"speed={auto_speed}, "
        f"pitch={auto_pitch}, "
        f"volume={auto_volume}"
    )

    # ===== END CONFIDENCE ENGINE =====
    # ===== ATTITUDE ENGINE =====
    detected_attitude, attitude_intensity = detect_attitude(speech_text)
    attitude_speed, attitude_pitch, attitude_volume = attitude_adjustments(
        detected_attitude,
        attitude_intensity
    )

    director.add_recommendation(
        "Attitude",
        speed=attitude_speed,
        pitch=attitude_pitch,
        volume=attitude_volume,
        confidence=float(attitude_intensity),
        reason=f"Attitude: {detected_attitude}"
    )

    auto_speed = float(auto_speed) + attitude_speed
    auto_pitch = float(auto_pitch) + attitude_pitch
    auto_volume = float(auto_volume) + attitude_volume

    auto_speed, auto_pitch, auto_volume = clamp_emotion_values(
        auto_speed,
        auto_pitch,
        auto_volume
    )

    print(
        f"Attitude: {detected_attitude} "
        f"(intensity {attitude_intensity}%) | "
        f"speed={auto_speed}, "
        f"pitch={auto_pitch}, "
        f"volume={auto_volume}"
    )

    # ===== END ATTITUDE ENGINE =====

    # ===== EXCITEMENT ENGINE =====
    detected_excitement, excitement_intensity = detect_excitement(speech_text)
    excitement_speed, excitement_pitch, excitement_volume = excitement_adjustments(
        detected_excitement,
        excitement_intensity
    )

    director.add_recommendation(
        "Excitement",
        speed=excitement_speed,
        pitch=excitement_pitch,
        volume=excitement_volume,
        confidence=float(excitement_intensity),
        reason=f"Excitement: {detected_excitement}"
    )

    auto_speed = float(auto_speed) + excitement_speed
    auto_pitch = float(auto_pitch) + excitement_pitch
    auto_volume = float(auto_volume) + excitement_volume

    auto_speed, auto_pitch, auto_volume = clamp_emotion_values(
        auto_speed,
        auto_pitch,
        auto_volume
    )

    print(
        f"Excitement: {detected_excitement} "
        f"(intensity {excitement_intensity}%) | "
        f"speed={auto_speed}, "
        f"pitch={auto_pitch}, "
        f"volume={auto_volume}"
    )

    # ===== END EXCITEMENT ENGINE =====

    # ===== ANGER / FRUSTRATION ENGINE =====
    detected_anger, anger_intensity = detect_anger(speech_text)
    anger_speed, anger_pitch, anger_volume = anger_adjustments(
        detected_anger,
        anger_intensity
    )

    director.add_recommendation(
        "Anger/Frustration",
        speed=anger_speed,
        pitch=anger_pitch,
        volume=anger_volume,
        confidence=float(anger_intensity),
        reason=f"Anger/Frustration: {detected_anger}"
    )

    auto_speed = float(auto_speed) + anger_speed
    auto_pitch = float(auto_pitch) + anger_pitch
    auto_volume = float(auto_volume) + anger_volume

    auto_speed, auto_pitch, auto_volume = clamp_emotion_values(
        auto_speed,
        auto_pitch,
        auto_volume
    )

    print(
        f"Anger/Frustration: {detected_anger} "
        f"(intensity {anger_intensity}%) | "
        f"speed={auto_speed}, "
        f"pitch={auto_pitch}, "
        f"volume={auto_volume}"
    )

    # ===== END ANGER / FRUSTRATION ENGINE =====

    # ===== HAPPINESS / PLAYFULNESS ENGINE =====
    detected_happiness, happiness_intensity = detect_happiness(speech_text)
    happiness_speed, happiness_pitch, happiness_volume = happiness_adjustments(
        detected_happiness,
        happiness_intensity
    )

    director.add_recommendation(
        "Happiness/Playfulness",
        speed=happiness_speed,
        pitch=happiness_pitch,
        volume=happiness_volume,
        confidence=float(happiness_intensity),
        reason=f"Happiness/Playfulness: {detected_happiness}"
    )

    auto_speed = float(auto_speed) + happiness_speed
    auto_pitch = float(auto_pitch) + happiness_pitch
    auto_volume = float(auto_volume) + happiness_volume

    auto_speed, auto_pitch, auto_volume = clamp_emotion_values(
        auto_speed,
        auto_pitch,
        auto_volume
    )

    print(
        f"Happiness/Playfulness: {detected_happiness} "
        f"(intensity {happiness_intensity}%) | "
        f"speed={auto_speed}, "
        f"pitch={auto_pitch}, "
        f"volume={auto_volume}"
    )

    # ===== END HAPPINESS / PLAYFULNESS ENGINE =====

    # ===== SADNESS / SERIOUSNESS ENGINE =====
    detected_sadness_mode, sadness_level, sadness_intensity = detect_sadness_seriousness(speech_text)

    sadness_speed, sadness_pitch, sadness_volume = sadness_seriousness_adjustments(
        detected_sadness_mode,
        sadness_level,
        sadness_intensity
    )

    director.add_recommendation(
        "Sadness/Seriousness",
        speed=sadness_speed,
        pitch=sadness_pitch,
        volume=sadness_volume,
        confidence=float(sadness_intensity),
        reason=f"Sadness/Seriousness: {detected_sadness_mode}"
    )

    auto_speed = float(auto_speed) + sadness_speed
    auto_pitch = float(auto_pitch) + sadness_pitch
    auto_volume = float(auto_volume) + sadness_volume

    auto_speed, auto_pitch, auto_volume = clamp_emotion_values(
        auto_speed,
        auto_pitch,
        auto_volume
    )

    print(
        f"Sadness/Seriousness: {detected_sadness_mode} "
        f"(level {sadness_level}, intensity {sadness_intensity}%) | "
        f"speed={auto_speed}, "
        f"pitch={auto_pitch}, "
        f"volume={auto_volume}"
    )

    # ===== END SADNESS / SERIOUSNESS ENGINE =====
    sentences = split_emotion_sentences(speech_text)

    # If there is only one sentence, keep the normal generation path.
    if len(sentences) <= 1:

        detected_emotion, emotion_intensity, speed_delta, pitch_delta, volume_delta = (
            emotion_adjustment_for_sentence(speech_text)
        )

        final_speed = float(auto_speed) + speed_delta
        final_pitch = float(auto_pitch) + pitch_delta
        final_volume = float(auto_volume) + volume_delta

        final_speed, final_pitch, final_volume = clamp_emotion_values(
            final_speed,
            final_pitch,
            final_volume
        )

        print(
            f"Emotion variation: {detected_emotion} "
            f"({emotion_intensity}%) | "
            f"speed={final_speed}, pitch={final_pitch}, volume={final_volume}"
        )

        # ===== MASTER DIRECTOR FINAL RESOLUTION =====
        director_decision = director.resolve()

        final_speed = director_decision.speed
        final_pitch = director_decision.pitch
        final_volume = director_decision.volume

        print(
            f"MASTER DIRECTOR RESOLVED | "
            f"speed={final_speed}, "
            f"pitch={final_pitch}, "
            f"volume={final_volume}"
        )

        rate = edge_rate(str(final_speed))
        pitch = edge_pitch(str(final_pitch))
        volume = edge_volume(str(final_volume))

        try:
            communicate = edge_tts.Communicate(
                speech_text,
                request.voice,
                rate=rate,
                pitch=pitch,
                volume=volume
            )

            await communicate.save(output_path)

        except Exception as error:
            print("Edge-TTS error:", error)
            raise HTTPException(
                status_code=500,
                detail=f"Voice generation failed: {error}"
            )

        return {
            "filename": filename,
            "url": f"/audio/{filename}",
            "emotion": detected_emotion,
            "emotion_intensity": emotion_intensity
        }

    # ===== MULTI-SENTENCE EMOTION GENERATION =====

    import tempfile
    import shutil
    import imageio_ffmpeg
    from pydub import AudioSegment

    AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
    AudioSegment.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    temp_dir = tempfile.mkdtemp(
        prefix="emotion_variation_",
        dir=OUTPUT_DIR
    )

    segments = []

    try:

        for index, sentence in enumerate(sentences):

            (
                detected_emotion,
                emotion_intensity,
                speed_delta,
                pitch_delta,
                volume_delta
            ) = emotion_adjustment_for_sentence(sentence)

            transition_factor = 1.0
            if index > 0:
                transition_factor = 0.65

            # ============================================================
            # TRUE MULTI-SENTENCE MASTER DIRECTOR PIPELINE
            #
            # Auto Voice Intelligence = BASELINE
            # Individual engines = DELTAS
            # Master Director = FINAL CONFLICT RESOLVER
            # ============================================================

            director.reset()

            director.set_baseline(
                speed=float(auto_speed),
                pitch=float(auto_pitch),
                volume=float(auto_volume),
            )

            # ===== EMOTION ENGINE RECOMMENDATION =====
            director.add_recommendation(
                "Emotion Variation",
                speed=speed_delta * transition_factor,
                pitch=pitch_delta * transition_factor,
                volume=volume_delta * transition_factor,
                confidence=max(1.0, float(emotion_intensity)),
                reason=(
                    f"Emotion: {detected_emotion} "
                    f"sentence {index + 1}"
                )
            )

            # ===== CONVERSATIONAL DELIVERY RECOMMENDATION =====
            conversation_speed, conversation_pitch, conversation_volume = (
                conversational_delivery_adjustments(
                    sentence,
                    index
                )
            )

            director.add_recommendation(
                "Conversational Delivery",
                speed=conversation_speed,
                pitch=conversation_pitch,
                volume=conversation_volume,
                confidence=60.0,
                reason=f"Conversational delivery: sentence {index + 1}"
            )

            # ===== NATURAL FOCUS RECOMMENDATION =====
            focus_speed, focus_pitch, focus_volume = (
                natural_focus_adjustments(sentence)
            )

            director.add_recommendation(
                "Natural Focus",
                speed=focus_speed,
                pitch=focus_pitch,
                volume=focus_volume,
                confidence=50.0,
                reason=f"Natural focus: sentence {index + 1}"
            )

            # ===== MASTER DIRECTOR FINAL RESOLUTION =====
            director_decision = director.resolve()

            sentence_speed = director_decision.speed
            sentence_pitch = director_decision.pitch
            sentence_volume = director_decision.volume

            (
                sentence_speed,
                sentence_pitch,
                sentence_volume
            ) = clamp_emotion_values(
                sentence_speed,
                sentence_pitch,
                sentence_volume
            )

            print(
                f"Conversational delivery [{index + 1}/{len(sentences)}] | "
                f"speed={sentence_speed}, "
                f"pitch={sentence_pitch}, "
                f"volume={sentence_volume}"
            )

            # ===== END CONVERSATIONAL DELIVERY =====

            (
                sentence_speed,
                sentence_pitch,
                sentence_volume
            ) = clamp_emotion_values(
                sentence_speed,
                sentence_pitch,
                sentence_volume
            )

            print(
                f"Emotion variation [{index + 1}/{len(sentences)}]: "
                f"{detected_emotion} "
                f"(intensity {emotion_intensity}%) | "
                f"speed={sentence_speed}, "
                f"pitch={sentence_pitch}, "
                f"volume={sentence_volume}"
            )

            segment_path = os.path.join(
                temp_dir,
                f"segment_{index:03d}.mp3"
            )

            # ===== FINAL MULTI-SENTENCE DIRECTOR VALUES =====
            resolved_sentence_speed = sentence_speed
            resolved_sentence_pitch = sentence_pitch
            resolved_sentence_volume = sentence_volume

            print(
                f"MASTER DIRECTOR SENTENCE RESOLVED | "
                f"speed={resolved_sentence_speed}, "
                f"pitch={resolved_sentence_pitch}, "
                f"volume={resolved_sentence_volume}"
            )

            communicate = edge_tts.Communicate(
                sentence,
                request.voice,
                rate=edge_rate(str(resolved_sentence_speed)),
                pitch=edge_pitch(str(resolved_sentence_pitch)),
                volume=edge_volume(str(resolved_sentence_volume))
            )

            print(f"TTS DEBUG | voice={request.voice} | rate={edge_rate(str(sentence_speed))} | pitch={edge_pitch(str(sentence_pitch))} | volume={edge_volume(str(sentence_volume))}")
            await communicate.save(segment_path)

            segments.append(segment_path)

        # Combine all emotional segments into one MP3 without ffprobe.
        import subprocess

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        combined = AudioSegment.empty()

        for index, segment_path in enumerate(segments):
            wav_path = os.path.join(
                temp_dir,
                f"segment_{index:03d}.wav"
            )

            subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",
                    "-i",
                    segment_path,
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    wav_path
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            segment = AudioSegment.from_wav(wav_path)
            combined += segment

        combined = voice_warmth_presence(combined)

        combined.export(
            output_path,
            format="mp3"
        )

        print(
            f"Emotion variation complete: "
            f"{len(segments)} sentence segments combined."
        )

    except Exception as error:

        print("Emotion variation error:", error)

        raise HTTPException(
            status_code=500,
            detail=f"Emotion variation failed: {error}"
        )

    finally:

        try:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )
        except Exception:
            pass

    return {
        "filename": filename,
        "url": f"/audio/{filename}",
        "emotion": "varied",
        "emotion_intensity": 100
    }


@app.get("/audio/{filename}")
async def get_audio(filename: str):

    file_path = os.path.join(
        OUTPUT_DIR,
        filename
    )

    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=404,
            detail="Audio file not found."
        )

    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename
    )

