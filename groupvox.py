import os
import librosa
from pydub import AudioSegment

def detect_vocal_segments(file_path, top_db=30):
    y, sr = librosa.load(file_path, sr=None)
    non_silent_intervals = librosa.effects.split(y, top_db=top_db)
    merged_intervals = []
    last_end = 0

    # Merge close segments
    for start, end in non_silent_intervals:
        start_sec = start / sr
        end_sec = end / sr
        if start_sec - last_end <= 1.0:  # Merge segments closer than 1 second
            merged_intervals[-1] = (merged_intervals[-1][0], end_sec)
        else:
            merged_intervals.append((start_sec, end_sec))
        last_end = end_sec

    return merged_intervals

def check_no_overlap(group_segments, new_segments):
    # Ensure there is no overlap between any of the new segments and the segments already in the group
    for existing_start, existing_end in group_segments:
        for new_start, new_end in new_segments:
            if not (new_end <= existing_start or new_start >= existing_end):
                return False  # Overlap found
    return True
    
def merge_segments(segments):
    sorted_segments = sorted(segments, key=lambda x: x[0])
    merged = []
    for start, end in sorted_segments:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return merged

def group_tracks(vocal_segments):
    groups = []
    for file, segments in vocal_segments.items():
        placed = False
        for group in groups:
            if check_no_overlap(group['segments'], segments):
                group['files'].append(file)
                group['segments'].extend(segments)
                group['segments'] = merge_segments(group['segments'])
                placed = True
                break
        if not placed:
            groups.append({'files': [file], 'segments': segments})
    return groups

def fix_overlapping_groups(groups):
    # Fix overlapping segments within each group
    for group in groups:
        group['segments'] = merge_segments(group['segments'])

def combine_tracks(group_files, vocal_segments):
    # Calculate the maximum length needed for the combined track
    max_length = 0
    for file in group_files:
        file_segments = vocal_segments[file]
        if file_segments:
            last_segment_end = file_segments[-1][1]  # Get the end time of the last segment
            max_length = max(max_length, last_segment_end)

    # Create an empty sound segment that spans this maximum length
    combined = AudioSegment.silent(duration=int(max_length * 1000))  # Convert to milliseconds

    # Overlay each file's segments onto the combined track
    for file in group_files:
        sound = AudioSegment.from_file(file)
        for start, end in vocal_segments[file]:
            segment = sound[start * 1000:end * 1000]  # Extract the segment
            combined = combined.overlay(segment, position=int(start * 1000))

    return combined if combined and len(combined) > 0 else None

def save_combined_tracks(groups, vocal_segments, output_directory):
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    for i, group in enumerate(groups):
        combined_track = combine_tracks(group['files'], vocal_segments)
        if combined_track:  # Only save if the track is not empty
            output_path = os.path.join(output_directory, f"grouped_vox_{i+1}.wav")
            combined_track.export(output_path, format="wav")
            print(f"Saved combined track: {output_path}")
        else:
            print(f"No audio to save for group {i+1}")

def main(directory, output_directory):
    files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.wav') or f.endswith('.aif')]
    vocal_segments = {file: detect_vocal_segments(file) for file in files}

    groups = group_tracks(vocal_segments)

    # Fix overlapping segments within each group
    fix_overlapping_groups(groups)

    for i, group in enumerate(groups):
        print(f"Group {i+1}:")
        for file in group['files']:
            segments = vocal_segments[file]
            formatted_segments = []
            for start, end in segments:
                start_min, start_sec = divmod(start, 60)
                end_min, end_sec = divmod(end, 60)
                start_sec = round(start_sec)
                end_sec = round(end_sec)
                formatted_segments.append(f"({int(start_min):02d}:{int(start_sec):02d} - {int(end_min):02d}:{int(end_sec):02d})")
            segments_str = ', '.join(formatted_segments)
            print(f"{os.path.basename(file)}: {segments_str}")
        print("\n")

    save_combined_tracks(groups, vocal_segments, output_directory)

if __name__ == "__main__":
    main('../johns_tracks/vocals', '../johns_tracks/vocals_grouped')
