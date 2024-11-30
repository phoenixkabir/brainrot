import wave
import pyaudio
from pydub import AudioSegment, silence
import asyncio
from hume import HumeStreamClient
from hume.models.config import ProsodyConfig
import speech_recognition as sr
import ollama
import threading
import time
from groq import Groq
import os

# Create a PyAudio object
p = pyaudio.PyAudio()

# Set up constants for the audio file
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 30
WAVE_OUTPUT_FILENAME = "output.wav"

# # Open a new stream
# stream = p.open(format=FORMAT,
#                 channels=CHANNELS,
#                 rate=RATE,
#                 input=True,
#                 frames_per_buffer=CHUNK)

print("* recording")

# frames = []

# # Record audio
# for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
#     data = stream.read(CHUNK)
#     frames.append(data)

print("* done recording")

# # Stop the stream
# stream.stop_stream()
# stream.close()
# p.terminate()

# # Write the audio data to a WAV file
# wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
# wf.setnchannels(CHANNELS)
# wf.setsampwidth(p.get_sample_size(FORMAT))
# wf.setframerate(RATE)
# wf.writeframes(b''.join(frames))
# wf.close()

# print("* recording")
# def delayed_print():
#     time.sleep(30)  # Wait for 30 seconds
#     print("* done recording")

# # Start the delayed print in a new thread
# thread = threading.Thread(target=delayed_print)
# thread.start()

# Load the audio file
audio = AudioSegment.from_wav(WAVE_OUTPUT_FILENAME)

# Split the audio into 6 parts - for 30 second audio file 
segment_length = len(audio) // 6 
audio_segments = [audio[i * segment_length:(i + 1) * segment_length] for i in range(6)]

# Initialize list to store results
new_list = []
emotions = []
text_segments = []

# Function to convert complete audio from speech to text
def stt_full() :
    recognizer = sr.Recognizer()
    with sr.AudioFile("output.wav") as source:
        audio_data = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio_data)
        # print(f"Extracted Text for segment {segment_index}: {text}")
        text_segments.append(f"Complete answer: {text}")
    except sr.UnknownValueError:
        print(f"Google Web Speech could not understand the audio in full answer")
    except sr.RequestError:
        print(f"Could not request results from Google Web Speech API for segment full answer")

# Function to process each audio segment with Hume API and STT
async def process_segment(segment, segment_index):
    segment_filename = f"output_segment_{segment_index}.wav"
    segment.export(segment_filename, format="wav") 

    client = HumeStreamClient("CJffluuY10Z47dNMZSMs4WQ7eBparPq0XYWJduyczGMk9OQO")
    config = ProsodyConfig()

    async with client.connect([config]) as socket:
        result = await socket.send_file(segment_filename)
        result = await socket.send_file(segment_filename)
        result = result['prosody']['predictions'][0]["emotions"]


    top_3_emotions = sorted(result, key=lambda x: x['score'], reverse=True)[:3]
    new_list.append(top_3_emotions)

    # Print top 3 emotions for the segment
    current_emotions = []
    for emotion in top_3_emotions:
        # print(f"{emotion['name']} : {emotion['score']}")
        current_emotions.append(f"{emotion['name']} : {emotion['score']}")
    
    emotions.append(current_emotions)

    # Perform STT on the segment
    recognizer = sr.Recognizer()
    with sr.AudioFile(segment_filename) as source:
        audio_data = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio_data)
        # print(f"Extracted Text for segment {segment_index}: {text}")
        text_segments.append(f"Text for segment {segment_index}: {text}")
    except sr.UnknownValueError:
        print(f"Google Web Speech could not understand the audio in segment {segment_index}")
    except sr.RequestError:
        print(f"Could not request results from Google Web Speech API for segment {segment_index}")

def print_output() :
    for i in range(len(emotions)) :
        print(f"Top 3 emotions for segment {i+1} :")
        print(emotions[i][0])
        print(emotions[i][1])
        print(emotions[i][2]+"\n")

def generate_summary(emotions, text_segments, question) :
    prompt = f"""
You have to judge the user's answer according to what they have spoken (text) and how they have spoken (emotions). The user does not know that the text has been divided into segments so just give a summary, give tips to the user about where and how they can improve.

question : {question}

{text_segments[-1]}

{text_segments[0]}
{text_segments[1]}
{text_segments[2]}
{text_segments[3]}
{text_segments[4]}
{text_segments[5]}

Top 3 emotions for segment 0:
{emotions[0][0]}
{emotions[0][1]}
{emotions[0][2]}

Top 3 emotions for segment 1:
{emotions[1][0]}
{emotions[1][1]}
{emotions[1][2]}

Top 3 emotions for segment 2:
{emotions[2][0]}
{emotions[2][1]}
{emotions[2][2]}

Top 3 emotions for segment 3:
{emotions[3][0]}
{emotions[3][1]}
{emotions[3][2]}

Top 3 emotions for segment 4:
{emotions[4][0]}
{emotions[4][1]}
{emotions[4][2]}

Top 3 emotions for segment 5:
{emotions[5][0]}
{emotions[5][1]}
{emotions[5][2]}
"""
    # output = ollama.generate(
    #     model="llama3.1",
    #     prompt=prompt,
    # )
    # return output["response"]
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    chat_completion = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": prompt,
        }
        ],
        model="llama-3.1-8b-instant",
    )

    print(chat_completion.choices[0].message.content)

def delete_files() :
    import os
    os.remove("output.wav")
    for i in range(6) :
        os.remove(f"output_segment_{i}.wav")

# Process all segments sequentially
async def measurer():
    tasks = [process_segment(segment, i) for i, segment in enumerate(audio_segments)]
    await asyncio.gather(*tasks)  # Concurrently process segments

    stt_full()
    print(generate_summary(emotions, text_segments, "Introduce yourself"))
    print_output()
    delete_files()

asyncio.run(measurer())