//! 时间轴计算模块
//!
//! 根据BPM变化计算拍号与时间的对应关系

use crate::models::TimelineSegment;

/// 根据BPM列表生成时间轴段
///
/// # Arguments
/// * `bpm_list` - BPM列表 (beat, bpm)
/// * `tick_per_beat` - 每拍tick数
///
/// # Returns
/// 时间轴段列表
pub fn generate_timeline_segments(bpm_list: &[(f64, f64)], tick_per_beat: u32) -> Vec<TimelineSegment> {
    if bpm_list.is_empty() {
        // 默认120 BPM
        return vec![TimelineSegment {
            start_beat: 0.0,
            end_beat: f64::MAX,
            start_sec: 0.0,
            end_sec: f64::MAX,
            bpm: 120.0,
        }];
    }

    let mut segments = Vec::with_capacity(bpm_list.len());
    let mut current_sec = 0.0;

    for (i, &(beat, bpm)) in bpm_list.iter().enumerate() {
        if bpm <= 0.0 {
            continue;
        }

        let start_beat = beat;
        let end_beat = if i + 1 < bpm_list.len() {
            bpm_list[i + 1].0
        } else {
            f64::MAX
        };

        // 计算该段的起始时间
        if i > 0 {
            let prev_segment: &TimelineSegment = &segments[i - 1];
            let beats_in_segment = start_beat - prev_segment.start_beat;
            let seconds_per_beat = 60.0 / prev_segment.bpm;
            current_sec = prev_segment.start_sec + beats_in_segment * seconds_per_beat;
        }

        // 计算该段的结束时间
        let beats_in_segment = end_beat - start_beat;
        let seconds_per_beat = 60.0 / bpm;
        let end_sec = if end_beat == f64::MAX {
            f64::MAX
        } else {
            current_sec + beats_in_segment * seconds_per_beat
        };

        segments.push(TimelineSegment {
            start_beat,
            end_beat,
            start_sec: current_sec,
            end_sec,
            bpm,
        });
    }

    segments
}

/// 将tick转换为秒
///
/// # Arguments
/// * `tick` - tick值
/// * `tick_per_beat` - 每拍tick数
/// * `segments` - 时间轴段列表
///
/// # Returns
/// 时间（秒）
pub fn tick_to_sec(tick: u32, tick_per_beat: u32, segments: &[TimelineSegment]) -> f64 {
    let beat = tick as f64 / tick_per_beat as f64;
    beat_to_sec(beat, segments)
}

/// 将拍号转换为秒
///
/// # Arguments
/// * `beat` - 拍号
/// * `segments` - 时间轴段列表
///
/// # Returns
/// 时间（秒）
pub fn beat_to_sec(beat: f64, segments: &[TimelineSegment]) -> f64 {
    for segment in segments {
        if beat >= segment.start_beat && beat < segment.end_beat {
            let beats_from_start = beat - segment.start_beat;
            let seconds_per_beat = 60.0 / segment.bpm;
            return segment.start_sec + beats_from_start * seconds_per_beat;
        }
    }

    // 如果超出所有段，使用最后一段的BPM继续计算
    if let Some(last) = segments.last() {
        let beats_from_start = beat - last.start_beat;
        let seconds_per_beat = 60.0 / last.bpm;
        last.start_sec + beats_from_start * seconds_per_beat
    } else {
        0.0
    }
}

/// 将秒转换为tick
///
/// # Arguments
/// * `sec` - 时间（秒）
/// * `tick_per_beat` - 每拍tick数
/// * `segments` - 时间轴段列表
///
/// # Returns
/// tick值
pub fn sec_to_tick(sec: f64, tick_per_beat: u32, segments: &[TimelineSegment]) -> u32 {
    let beat = sec_to_beat(sec, segments);
    (beat * tick_per_beat as f64) as u32
}

/// 将秒转换为拍号
///
/// # Arguments
/// * `sec` - 时间（秒）
/// * `segments` - 时间轴段列表
///
/// # Returns
/// 拍号
pub fn sec_to_beat(sec: f64, segments: &[TimelineSegment]) -> f64 {
    for segment in segments {
        if sec >= segment.start_sec && sec < segment.end_sec {
            let seconds_from_start = sec - segment.start_sec;
            let beats_per_second = segment.bpm / 60.0;
            return segment.start_beat + seconds_from_start * beats_per_second;
        }
    }

    // 如果超出所有段，使用最后一段的BPM继续计算
    if let Some(last) = segments.last() {
        let seconds_from_start = sec - last.start_sec;
        let beats_per_second = last.bpm / 60.0;
        last.start_beat + seconds_from_start * beats_per_second
    } else {
        0.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_timeline_segments() {
        let bpm_list = vec![(0.0, 120.0), (4.0, 180.0)];
        let segments = generate_timeline_segments(&bpm_list, 96);

        assert_eq!(segments.len(), 2);
        assert_eq!(segments[0].bpm, 120.0);
        assert_eq!(segments[0].start_beat, 0.0);
        assert_eq!(segments[0].start_sec, 0.0);

        // 第一段4拍，120BPM = 0.5秒/拍
        assert!((segments[0].end_sec - 2.0).abs() < 0.001);

        assert_eq!(segments[1].bpm, 180.0);
        assert_eq!(segments[1].start_beat, 4.0);
        assert!((segments[1].start_sec - 2.0).abs() < 0.001);
    }

    #[test]
    fn test_beat_to_sec() {
        let segments = vec![
            TimelineSegment {
                start_beat: 0.0,
                end_beat: 4.0,
                start_sec: 0.0,
                end_sec: 2.0,
                bpm: 120.0,
            },
        ];

        // 120 BPM = 0.5秒/拍
        assert!((beat_to_sec(0.0, &segments) - 0.0).abs() < 0.001);
        assert!((beat_to_sec(2.0, &segments) - 1.0).abs() < 0.001);
        assert!((beat_to_sec(4.0, &segments) - 2.0).abs() < 0.001);
    }
}
