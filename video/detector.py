import os
import csv
import cv2
from datetime import timedelta
from deep_sort_realtime.deepsort_tracker import DeepSort
from ultralytics import YOLO

# 저장 폴더 준비
os.makedirs('captured_frames', exist_ok=True)
os.makedirs('captured_crops', exist_ok=True)

# 모델 로드 (YOLOv8)
model = YOLO('yolov8n.pt')  # 더 높은 정확도가 필요하면 yolov8m.pt 사용 가능

# DeepSORT 초기화
tracker = DeepSort(max_age=30)

# 비디오 열기
video_path = 'samples/06.wander/529-3/529-3_cam01_wander02_place08_night_spring.mp4'
cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS)

frame_idx = 0

# 상태 저장용
active_tracks = {}  # {ID: {'start_frame':..., 'start_time':...}}
finished_tracks = []  # 완료된 사람 기록

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame_idx += 1
    results = model.predict(frame, verbose=False)[0]

    detections = []

    for result in results.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = result

        # 사람만 감지
        if int(class_id) == 0 and score > 0.4:
            detections.append(([x1, y1, x2 - x1, y2 - y1], score, 'person'))

    tracks = tracker.update_tracks(detections, frame=frame)

    current_ids = set()

    for track in tracks:
        if not track.is_confirmed():
            continue

        track_id = track.track_id
        l, t, r, b = map(int, track.to_ltrb())

        current_ids.add(track_id)

        # 새로 등장한 사람 처리
        if track_id not in active_tracks:
            # 등장 시각 저장
            start_time_sec = frame_idx / fps
            active_tracks[track_id] = {
                'start_frame': frame_idx,
                'start_time_sec': start_time_sec,
            }

            # 현재 시간 문자열
            time_in_video = str(timedelta(seconds=int(start_time_sec)))

            # 전체 프레임 저장
            frame_filename = f'captured_frames/frame_{frame_idx:06d}_id_{track_id}.jpg'
            cv2.rectangle(frame, (l, t), (r, b), (0, 255, 0), 2)
            cv2.putText(frame, f"ID {track_id}", (l, t - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.imwrite(frame_filename, frame)

            # Crop 저장
            crop = frame[t:b, l:r]
            crop_filename = f'captured_crops/crop_{frame_idx:06d}_id_{track_id}.jpg'
            cv2.imwrite(crop_filename, crop)

            print(f"[INFO] 사람 ID {track_id} 등장 @ {time_in_video} (프레임 {frame_idx})")

    # 사라진 사람 처리
    disappeared_ids = set(active_tracks.keys()) - current_ids

    for lost_id in disappeared_ids:
        end_time_sec = frame_idx / fps
        start_info = active_tracks.pop(lost_id)

        duration_sec = end_time_sec - start_info['start_time_sec']
        start_time_str = str(timedelta(seconds=int(start_info['start_time_sec'])))
        end_time_str = str(timedelta(seconds=int(end_time_sec)))
        duration_str = str(timedelta(seconds=int(duration_sec)))

        finished_tracks.append({
            'id': lost_id,
            'start_time': start_time_str,
            'end_time': end_time_str,
            'duration': duration_str
        })

        print(f"[INFO] 사람 ID {lost_id} 사라짐: 등장 {start_time_str} -> 종료 {end_time_str} (머문 시간 {duration_str})")

cap.release()
cv2.destroyAllWindows()

# 결과 CSV 파일로 저장
csv_filename = 'tracking_results.csv'
with open(csv_filename, mode='w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=['id', 'start_time', 'end_time', 'duration'])
    writer.writeheader()
    for record in finished_tracks:
        writer.writerow(record)

print(f"\n✅ 결과가 '{csv_filename}' 파일로 저장되었습니다.")

# 콘솔 최종 출력
print("\n=== 전체 추적 결과 ===")
for record in finished_tracks:
    print(f"ID {record['id']} : 등장 {record['start_time']} → 종료 {record['end_time']} (머문 시간 {record['duration']})")
