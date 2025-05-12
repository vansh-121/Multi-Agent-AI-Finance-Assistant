import speech_recognition as sr
from gtts import gTTS
import io
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoiceAgent:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def speech_to_text(self, audio_file):
        try:
            with sr.AudioFile(audio_file) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio)
                logger.info("Speech converted to text")
                return text
        except Exception as e:
            logger.error(f"Error in STT: {str(e)}")
            return ""

    def text_to_speech(self, text):
        try:
            tts = gTTS(text=text, lang='en')
            audio_file = io.BytesIO()
            tts.write_to_fp(audio_file)
            audio_file.seek(0)
            logger.info("Text converted to speech")
            return audio_file
        except Exception as e:
            logger.error(f"Error in TTS: {str(e)}")
            return None