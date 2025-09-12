import cv2
import mediapipe as mp
import time
from gtts import gTTS
import pygame
import os
import tempfile
import threading

# ==== ORV Dialog Class ====
class ORVDialog:
    def __init__(self):
        self.typing_index = 0
        self.last_type_time = 0
        self.typing_speed = 0.03
        self.dialog_start_time = 0
        self.dialog_duration = 5
        self.ui_alpha = 0.0
        self.current_message = ""
        self.last_gesture = None

    def draw(self, frame, gesture_data):
        if not gesture_data:
            return frame
        
        height, width = frame.shape[:2]
        current_time = time.time()

        full_message = gesture_data['message']

        # reset typing
        if full_message != self.current_message:
            self.typing_index = 0
            self.last_type_time = current_time
            self.current_message = full_message

        # typing effect
        if current_time - self.last_type_time > self.typing_speed:
            if self.typing_index < len(full_message):
                self.typing_index += 1
                self.last_type_time = current_time

        display_message = full_message[:self.typing_index]

        # box size & pos
        box_width = min(600, width - 40)
        box_height = 130
        box_x = (width - box_width) // 2
        box_y = height - box_height - 330

        # simple background
        overlay = frame.copy()
        cv2.rectangle(overlay, (box_x, box_y),
                      (box_x + box_width, box_y + box_height),
                      (20, 25, 35), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

        # border
        border_color = gesture_data['color']
        cv2.rectangle(frame, (box_x, box_y),
                      (box_x + box_width, box_y + box_height),
                      border_color, 2)

        # title
        cv2.putText(frame, f"◊ {gesture_data['name']} ◊",
                    (box_x + 20, box_y + 30),
                    cv2.FONT_HERSHEY_DUPLEX, 0.7, (255,255,255), 2)

        # message
        cv2.putText(frame, display_message,
                    (box_x + 20, box_y + 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220,220,255), 2)

        return frame

# ==== text to speech ====
class TTSHandler:
    def __init__(self):
        pygame.mixer.init()
        self.current_gesture = None
        self.is_playing = False
        self.temp_files = [] 
        
    def play_audio(self, text, lang='id'):
        def _play():
            try:
                # create file audio
                tts = gTTS(text=text, lang=lang, slow=False)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                temp_file.close()
                
                tts.save(temp_file.name)
                self.temp_files.append(temp_file.name)
                
                # load & play audio
                pygame.mixer.music.load(temp_file.name)
                pygame.mixer.music.play()
                
                # selesai
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)
                
                # hapus file setelah selesai
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
                    if temp_file.name in self.temp_files:
                        self.temp_files.remove(temp_file.name)
                
            except Exception as e:
                print(f"Error in TTS: {e}")
            finally:
                self.is_playing = False
                
        # jalankan di thread
        thread = threading.Thread(target=_play)
        thread.daemon = True
        thread.start()
    
    def cleanup(self):
        # bersihkan file temporer
        for file_path in self.temp_files:
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except:
                    pass
        self.temp_files = []

# ==== gesture detection ====
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False,
                       max_num_hands=2,
                       min_detection_confidence=0.7)
mp_drawing = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)
dialog = ORVDialog()
tts_handler = TTSHandler()

# mapping gesture -> pesan + warna + tts
gesture_map = {
    "Halo": {"name": "five fingers", "message": "Halooooo 👋", "color": (0, 0, 255), "tts_text": "Haloo!"},
    "OK": {"name": "OK", "message": "Okeee", "color": (0, 255, 0), "tts_text": "wokeee"},
    "I Love You": {"name": "Metal", "message": "Mari berteman dengan baik ❤️", "color": (255, 0, 100), "tts_text": "Mari berteman dengan baik"},
    "Peace": {"name": "two fingers", "message": "Jurusan Teknik Informatika", "color": (0, 255, 0), "tts_text": "Jurusan teknik informatika"},
    "Fist": {"name": "Fist", "message": "Semangat 👊", "color": (255, 255, 0), "tts_text": "Belok kanan"},
    "Sip": {"name": "Sip", "message": "Cihuyyyy", "color": (0, 100, 255), "tts_text": "cihuyyy"},
    "Pointing": {"name": "Pointing", "message": "Nama saya Muhamad Farel Fauzan", "color": (0, 100, 255), "tts_text": "Nama saya muhamad farel fauzan"},
    "Three Fingers Up": {"name": "three fingers", "message": "Asal sekolah dari SMKN 2 Kuningan", "color": (100, 200, 255), "tts_text": "Asal sekolah dari SMKN 2 Kuningan"},
    "Double": {"name": "easter egg", "message": "Absolute Cinema", "color": (0, 100, 255), "tts_text": "Absolute cinemaa"},
}

# untuk melacak gesture sebelumnya
last_gesture = None

try:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)
        gesture = ""

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    frame, hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(0,0,255), thickness=3, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(255,255,255), thickness=2)
                )
                lm = hand_landmarks.landmark

                # === Halo ===
                all_fingers_up = all(
                    lm[tip].y < lm[pip].y for tip, pip in [
                        (mp_hands.HandLandmark.THUMB_TIP, mp_hands.HandLandmark.THUMB_IP),
                        (mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.INDEX_FINGER_PIP),
                        (mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP),
                        (mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_PIP),
                        (mp_hands.HandLandmark.PINKY_TIP, mp_hands.HandLandmark.PINKY_PIP),
                    ]
                )
                if all_fingers_up: gesture = "Halo"

                # === Double Halo (10 Fingers) ===
                # Pastikan Anda memiliki akses ke landmark kedua tangan
                if results.multi_hand_landmarks and len(results.multi_hand_landmarks) == 2:
                    # ambil landmark dari kedua tangan
                    lm_left = results.multi_hand_landmarks[0].landmark
                    lm_right = results.multi_hand_landmarks[1].landmark
                    
                    # periksa apakah semua jari di kedua tangan terbuka
                    left_hand_open = all(
                        lm_left[tip].y < lm_left[pip].y for tip, pip in [
                            (mp_hands.HandLandmark.THUMB_TIP, mp_hands.HandLandmark.THUMB_IP),
                            (mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.INDEX_FINGER_PIP),
                            (mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP),
                            (mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_PIP),
                            (mp_hands.HandLandmark.PINKY_TIP, mp_hands.HandLandmark.PINKY_PIP),
                        ]
                    )
                    
                    right_hand_open = all(
                        lm_right[tip].y < lm_right[pip].y for tip, pip in [
                            (mp_hands.HandLandmark.THUMB_TIP, mp_hands.HandLandmark.THUMB_IP),
                            (mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.INDEX_FINGER_PIP),
                            (mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP),
                            (mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_PIP),
                            (mp_hands.HandLandmark.PINKY_TIP, mp_hands.HandLandmark.PINKY_PIP),
                        ]
                    )
                    
                    if left_hand_open and right_hand_open:
                        gesture = "Double"

                # === ichi ===
                index_finger_up = (
                    lm[mp_hands.HandLandmark.INDEX_FINGER_TIP].y < lm[mp_hands.HandLandmark.INDEX_FINGER_PIP].y and
                    lm[mp_hands.HandLandmark.INDEX_FINGER_PIP].y < lm[mp_hands.HandLandmark.INDEX_FINGER_MCP].y
                )

                other_fingers_down = all(
                    lm[tip].y > lm[pip].y for tip, pip in [
                        (mp_hands.HandLandmark.THUMB_TIP, mp_hands.HandLandmark.THUMB_IP),
                        (mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP),
                        (mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_PIP),
                        (mp_hands.HandLandmark.PINKY_TIP, mp_hands.HandLandmark.PINKY_PIP),
                    ]
                )

                if index_finger_up and other_fingers_down:
                    gesture = "Pointing"

                # === OK ===
                thumb_index_close = (
                    abs(lm[mp_hands.HandLandmark.THUMB_TIP].x - lm[mp_hands.HandLandmark.INDEX_FINGER_TIP].x) < 0.05 and
                    abs(lm[mp_hands.HandLandmark.THUMB_TIP].y - lm[mp_hands.HandLandmark.INDEX_FINGER_TIP].y) < 0.05
                )
                middle_up = lm[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y < lm[mp_hands.HandLandmark.MIDDLE_FINGER_PIP].y
                if thumb_index_close and middle_up: gesture = "OK"

                # === I Love You ===
                love_you = (
                    lm[mp_hands.HandLandmark.THUMB_TIP].y < lm[mp_hands.HandLandmark.THUMB_IP].y and
                    lm[mp_hands.HandLandmark.INDEX_FINGER_TIP].y < lm[mp_hands.HandLandmark.INDEX_FINGER_PIP].y and
                    lm[mp_hands.HandLandmark.PINKY_TIP].y < lm[mp_hands.HandLandmark.PINKY_PIP].y and
                    lm[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y > lm[mp_hands.HandLandmark.MIDDLE_FINGER_PIP].y and
                    lm[mp_hands.HandLandmark.RING_FINGER_TIP].y > lm[mp_hands.HandLandmark.RING_FINGER_PIP].y
                )
                if love_you: gesture = "I Love You"

                # === Peace ===
                index_up = lm[mp_hands.HandLandmark.INDEX_FINGER_TIP].y < lm[mp_hands.HandLandmark.INDEX_FINGER_PIP].y
                middle_up = lm[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y < lm[mp_hands.HandLandmark.MIDDLE_FINGER_PIP].y
                ring_down = lm[mp_hands.HandLandmark.RING_FINGER_TIP].y > lm[mp_hands.HandLandmark.RING_FINGER_PIP].y
                pinky_down = lm[mp_hands.HandLandmark.PINKY_TIP].y > lm[mp_hands.HandLandmark.PINKY_PIP].y
                thumb_down = lm[mp_hands.HandLandmark.THUMB_TIP].y > lm[mp_hands.HandLandmark.THUMB_IP].y
                if index_up and middle_up and ring_down and pinky_down and thumb_down: gesture = "Peace"

                # === Three Fingers Detailed ===
                three_fingers_detailed = (
                    # Jari telunjuk terangkat
                    lm[mp_hands.HandLandmark.INDEX_FINGER_TIP].y < lm[mp_hands.HandLandmark.INDEX_FINGER_PIP].y and
                    lm[mp_hands.HandLandmark.INDEX_FINGER_PIP].y < lm[mp_hands.HandLandmark.INDEX_FINGER_MCP].y and
                    
                    # Jari tengah terangkat
                    lm[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y < lm[mp_hands.HandLandmark.MIDDLE_FINGER_PIP].y and
                    lm[mp_hands.HandLandmark.MIDDLE_FINGER_PIP].y < lm[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].y and
                    
                    # Jari manis terangkat
                    lm[mp_hands.HandLandmark.RING_FINGER_TIP].y < lm[mp_hands.HandLandmark.RING_FINGER_PIP].y and
                    lm[mp_hands.HandLandmark.RING_FINGER_PIP].y < lm[mp_hands.HandLandmark.RING_FINGER_MCP].y and
                    
                    # Ibu jari menutup
                    lm[mp_hands.HandLandmark.THUMB_TIP].y > lm[mp_hands.HandLandmark.THUMB_IP].y and
                    
                    # Kelingking menutup
                    lm[mp_hands.HandLandmark.PINKY_TIP].y > lm[mp_hands.HandLandmark.PINKY_PIP].y
                )

                if three_fingers_detailed:
                    gesture = "Three Fingers Up"

                # === Fist ===
                all_folded = all(
                    lm[tip].y > lm[pip].y for tip, pip in [
                        (mp_hands.HandLandmark.THUMB_TIP, mp_hands.HandLandmark.THUMB_IP),
                        (mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.INDEX_FINGER_PIP),
                        (mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP),
                        (mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_PIP),
                        (mp_hands.HandLandmark.PINKY_TIP, mp_hands.HandLandmark.PINKY_PIP),
                    ]
                )
                if all_folded: gesture = "Fist"

                # === Sip ===
                thumb_up = lm[mp_hands.HandLandmark.THUMB_TIP].y < lm[mp_hands.HandLandmark.THUMB_IP].y
                others_folded = all(
                    lm[tip].y > lm[pip].y for tip, pip in [
                        (mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.INDEX_FINGER_PIP),
                        (mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP),
                        (mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_PIP),
                        (mp_hands.HandLandmark.PINKY_TIP, mp_hands.HandLandmark.PINKY_PIP),
                    ]
                )
                if thumb_up and others_folded and not all_folded: gesture = "Sip"

        # tampilkan kotak Dialog jika gesture dikenali
        if gesture in gesture_map:
            dialog.draw(frame, gesture_map[gesture])
            
            # play audio jika gesture berubah dan tidak sedang memainkan audio
            if gesture != last_gesture and not tts_handler.is_playing:
                tts_handler.is_playing = True
                tts_handler.play_audio(gesture_map[gesture]["tts_text"])
                last_gesture = gesture
        else:
            last_gesture = None

        cv2.imshow("Gesture Recognition + ORV Dialog", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except Exception as e:
    print(f"Error occurred: {e}")
finally:
    cap.release()
    cv2.destroyAllWindows()
    tts_handler.cleanup()