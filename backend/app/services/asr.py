import assemblyai as aai
from app.config import settings

aai.settings.api_key = settings.ASSEMBLYAI_API_KEY

def transcribe(audio_url: str) -> str:
    cfg = aai.TranscriptionConfig(
        speech_models = ["universal-2"],
        speaker_labels = True,
        speakers_expected = 2,
        punctuate = True,
    )
    t = aai.Transcriber(config=cfg).transcribe(audio_url)

    if t.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI transcription failed: {t.error}")

    return "\n".join(f"Speaker {u.speaker}: {u.text}" for u in t.utterances)