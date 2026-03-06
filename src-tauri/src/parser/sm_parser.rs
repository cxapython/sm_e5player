//! SM文件解析器
//!
//! 解析StepMania格式的SM谱面文件

use crate::models::{ArrowEvent, ChartInfo, ChartData};
use crate::parser::timeline::generate_timeline_segments;
use regex::Regex;
use std::fs;

/// SM解析器
pub struct SmParser {
    /// 每拍tick数
    pub tick_per_beat: u32,
    /// aType映射（用于5列/10列谱面转换）
    pub atype_map: Vec<u8>,
}

impl Default for SmParser {
    fn default() -> Self {
        Self {
            tick_per_beat: 96,
            atype_map: vec![0, 1, 2, 3, 4], // 直接映射：列0=DownLeft, 列1=UpLeft, 列2=Center, 列3=UpRight, 列4=DownRight
        }
    }
}

impl SmParser {
    /// 创建新的SM解析器
    pub fn new() -> Self {
        Self::default()
    }

    /// 设置每拍tick数
    pub fn with_tick_per_beat(mut self, tick: u32) -> Self {
        self.tick_per_beat = tick;
        self
    }

    /// 解析SM文件
    ///
    /// # Arguments
    /// * `path` - SM文件路径
    ///
    /// # Returns
    /// (谱面信息, 谱面数据)
    pub fn parse_file(&self, path: &str) -> Result<(ChartInfo, ChartData), String> {
        let content = fs::read_to_string(path)
            .map_err(|e| format!("读取文件失败: {}", e))?;

        self.parse_content(&content)
    }

    /// 解析SM文件内容
    pub fn parse_content(&self, content: &str) -> Result<(ChartInfo, ChartData), String> {
        // 解析基本信息
        let title = self.extract_tag(content, "TITLE").unwrap_or_default();
        let subtitle = self.extract_tag(content, "SUBTITLE").unwrap_or_default();
        let artist = self.extract_tag(content, "ARTIST").unwrap_or_default();
        let offset: f64 = self.extract_tag(content, "OFFSET")
            .and_then(|s| s.parse().ok())
            .unwrap_or(0.0);

        // 解析BPM
        let bpm_str = self.extract_tag(content, "BPMS").unwrap_or_default();
        let bpm_list = self.parse_bpm_list(&bpm_str)?;

        // 解析DisplayBPM
        let display_bpm = self.extract_tag(content, "DISPLAYBPM")
            .unwrap_or_else(|| {
                if let Some(&(_, bpm)) = bpm_list.first() {
                    format!("{:.0}", bpm)
                } else {
                    "120".to_string()
                }
            });

        // 解析NOTES
        let notes_blocks = self.extract_notes_blocks(content)?;
        if notes_blocks.is_empty() {
            return Err("未找到NOTES区块".to_string());
        }

        // 使用第一个NOTES块
        let notes_block = &notes_blocks[0];
        let column_count = self.detect_column_count(notes_block);

        // 解析箭头事件
        let arrows = self.parse_arrow_events(notes_block, &bpm_list)?;

        // 计算总时长
        let total_duration = arrows.last()
            .map(|a| a.end_sec)
            .unwrap_or(0.0);

        let info = ChartInfo {
            title,
            subtitle,
            artist,
            offset,
            bpm_list: bpm_list.clone(),
            display_bpm,
            column_count,
            difficulty: String::new(),
        };

        let chart_data = ChartData {
            info: info.clone(),
            arrows,
            total_duration,
            total_notes: info.column_count as usize, // 简化计算
        };

        Ok((info, chart_data))
    }

    /// 提取标签值（匹配到分号、换行+注释、或下一个标签）
    fn extract_tag(&self, content: &str, tag: &str) -> Option<String> {
        // 查找 #TAG:
        let tag_start = format!("#{}:", tag);
        let start_idx = content.find(&tag_start)?;

        // 从 #TAG: 之后开始
        let value_start = start_idx + tag_start.len();

        // 从这里开始查找结束位置
        let remaining = &content[value_start..];

        // 逐字符查找结束位置
        let mut end_idx = 0;
        let chars: Vec<char> = remaining.chars().collect();

        for i in 0..chars.len() {
            let c = chars[i];

            // 分号是标签结束符
            if c == ';' {
                end_idx = i;
                break;
            }

            // 换行后跟 // 是注释，停止
            if c == '\n' || c == '\r' {
                // 检查下一行是否是注释或新标签
                let mut j = i + 1;
                // 跳过空白
                while j < chars.len() && (chars[j] == ' ' || chars[j] == '\t') {
                    j += 1;
                }
                // 如果是 // 注释或 # 新标签，在这里结束
                if j < chars.len() {
                    if chars[j] == '/' && j + 1 < chars.len() && chars[j + 1] == '/' {
                        end_idx = i;
                        break;
                    }
                    if chars[j] == '#' {
                        end_idx = i;
                        break;
                    }
                }
            }
        }

        let value = remaining[..end_idx].to_string();
        Some(value.trim().to_string())
    }

    /// 解析BPM列表
    fn parse_bpm_list(&self, bpm_str: &str) -> Result<Vec<(f64, f64)>, String> {
        if bpm_str.is_empty() {
            return Ok(vec![(0.0, 120.0)]);
        }

        let mut bpm_list = Vec::new();

        // 按逗号分割，取第一个有效值
        for pair in bpm_str.split(',') {
            let pair = pair.trim();
            if pair.is_empty() {
                continue;
            }

            // 按等号分割
            let parts: Vec<&str> = pair.split('=').collect();
            if parts.len() >= 2 {
                let beat_str = parts[0].trim();
                let bpm_str = parts[1].trim();

                // 只取数字部分（处理可能的注释）
                let beat: f64 = self.extract_number(beat_str)
                    .ok_or_else(|| format!("解析BPM拍号失败: {}", beat_str))?;

                let bpm: f64 = self.extract_number(bpm_str)
                    .ok_or_else(|| format!("解析BPM值失败: {}", bpm_str))?;

                if bpm > 0.0 {
                    bpm_list.push((beat, bpm));
                }
            }
        }

        if bpm_list.is_empty() {
            Ok(vec![(0.0, 120.0)])
        } else {
            Ok(bpm_list)
        }
    }

    /// 从字符串中提取数字
    fn extract_number(&self, s: &str) -> Option<f64> {
        // 移除注释（// 后的内容）
        let s = s.split("//").next().unwrap_or(s).trim();

        // 尝试直接解析
        if let Ok(n) = s.parse::<f64>() {
            return Some(n);
        }

        // 尝试提取数字
        let chars: Vec<char> = s.chars().collect();
        let mut start = 0;
        let mut end = chars.len();

        // 找到数字开始
        for (i, &c) in chars.iter().enumerate() {
            if c.is_ascii_digit() || c == '-' || c == '+' || c == '.' {
                start = i;
                break;
            }
        }

        // 找到数字结束
        for (i, &c) in chars.iter().enumerate().skip(start) {
            if !c.is_ascii_digit() && c != '.' && c != '-' && c != '+' {
                end = i;
                break;
            }
        }

        if start < end {
            s[start..end].parse::<f64>().ok()
        } else {
            None
        }
    }

    /// 提取NOTES区块
    fn extract_notes_blocks(&self, content: &str) -> Result<Vec<String>, String> {
        let re = Regex::new(r"#NOTES:\s*([^#]*?);")
            .map_err(|e| format!("编译正则失败: {}", e))?;

        let blocks: Vec<String> = re.captures_iter(content)
            .filter_map(|caps| caps.get(1).map(|m| m.as_str().trim().to_string()))
            .collect();

        if blocks.is_empty() {
            Err("未找到NOTES区块".to_string())
        } else {
            Ok(blocks)
        }
    }

    /// 检测列数
    fn detect_column_count(&self, notes_block: &str) -> usize {
        // 移除元数据行
        let lines: Vec<&str> = notes_block.lines().collect();
        let mut measure_start = 0;

        // 找到第一个小节（以//开头或第一个箭头数据）
        for (i, line) in lines.iter().enumerate() {
            let trimmed = line.trim();
            if trimmed.starts_with("//") || trimmed.contains('0') || trimmed.contains('1') {
                measure_start = i;
                break;
            }
        }

        // 统计列数
        for line in lines.iter().skip(measure_start) {
            let trimmed = line.trim();
            if trimmed.starts_with("//") || trimmed.is_empty() {
                continue;
            }
            // 只包含01的行是箭头数据
            if trimmed.chars().all(|c| c == '0' || c == '1' || c == '2' || c == '3' || c == 'M') {
                return trimmed.len();
            }
        }

        // 默认5列
        5
    }

    /// 解析箭头事件
    fn parse_arrow_events(
        &self,
        notes_block: &str,
        bpm_list: &[(f64, f64)],
    ) -> Result<Vec<ArrowEvent>, String> {
        let segments = generate_timeline_segments(bpm_list, self.tick_per_beat);
        let mut arrows = Vec::new();
        let mut current_beat = 0.0;
        let mut measure_idx = 0usize;
        let mut hold_starts: Vec<Option<(usize, f64)>> = vec![None; 10]; // 跟踪长按开始

        // 解析小节
        let measures: Vec<&str> = notes_block.split(',')
            .collect();

        for measure in measures {
            let lines: Vec<&str> = measure.lines().collect();
            let mut arrow_lines = Vec::new();

            for line in lines {
                let trimmed = line.trim();
                if trimmed.starts_with("//") || trimmed.is_empty() {
                    continue;
                }
                // 箭头数据行
                if trimmed.chars().all(|c| "0123M".contains(c)) {
                    arrow_lines.push(trimmed);
                }
            }

            if arrow_lines.is_empty() {
                continue;
            }

            // 计算每行的拍号增量
            let lines_per_beat = arrow_lines.len() as f64 / 4.0; // 4拍一小节
            let beat_increment = 1.0 / lines_per_beat.max(1.0);

            for (line_idx, line) in arrow_lines.iter().enumerate() {
                let beat = current_beat + line_idx as f64 * beat_increment;
                let sec = crate::parser::timeline::beat_to_sec(beat, &segments);

                for (track_idx, ch) in line.chars().enumerate() {
                    // 直接使用列索引作为轨道（0=DownLeft, 1=UpLeft, 2=Center, 3=UpRight, 4=DownRight）
                    let track = track_idx;

                    match ch {
                        '1' | 'M' => {
                            // 点按箭头
                            arrows.push(ArrowEvent {
                                track_idx: track as u8,
                                start_sec: sec,
                                end_sec: sec,
                                arrow_type: 0,
                            });
                        }
                        '2' => {
                            // 长按开始
                            if track < hold_starts.len() {
                                hold_starts[track] = Some((arrows.len(), sec));
                            }
                        }
                        '3' => {
                            // 长按结束
                            if track < hold_starts.len() {
                                if let Some((start_idx, start_sec)) = hold_starts[track].take() {
                                    // 更新长按事件
                                    if start_idx < arrows.len() {
                                        arrows[start_idx].end_sec = sec;
                                        arrows[start_idx].arrow_type = 1;
                                    }
                                }
                            }
                        }
                        _ => {}
                    }
                }
            }

            current_beat += 4.0; // 每小节4拍
            measure_idx += 1;
        }

        // 按时间排序
        arrows.sort_by(|a, b| {
            a.start_sec.partial_cmp(&b.start_sec).unwrap()
        });

        Ok(arrows)
    }

    /// 推荐aType映射
    pub fn recommend_atype_map(&self, column_count: usize) -> (Vec<u8>, bool) {
        match column_count {
            5 => {
                // E舞成名5列映射
                // DownLeft=1, UpLeft=2, Center=4, UpRight=6, DownRight=7
                (vec![1, 2, 4, 6, 7], true)
            }
            10 => {
                // E舞成名10列映射（双人）
                (vec![1, 2, 4, 6, 7, 1, 2, 4, 6, 7], true)
            }
            4 => {
                // 标准4列
                (vec![0, 1, 2, 3], false)
            }
            8 => {
                // 标准8列
                (vec![0, 1, 2, 3, 4, 5, 6, 7], false)
            }
            _ => {
                // 默认按索引映射
                (vec![1, 2, 4, 6, 7], true)
            }
        }
    }
}

/// 格式化秒数为时间字符串
pub fn format_seconds(seconds: f64) -> String {
    let total_secs = seconds.max(0.0) as u32;
    let mins = total_secs / 60;
    let secs = total_secs % 60;
    format!("{:02}:{:02}", mins, secs)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_tag() {
        let parser = SmParser::new();
        let content = "#TITLE:Test Song;";
        let result = parser.extract_tag(content, "TITLE");
        assert_eq!(result, Some("Test Song".to_string()));
    }

    #[test]
    fn test_parse_bpm_list() {
        let parser = SmParser::new();
        let bpm_str = "0.000=120.000,4.000=180.000";
        let result = parser.parse_bpm_list(bpm_str).unwrap();
        assert_eq!(result.len(), 2);
        assert_eq!(result[0], (0.0, 120.0));
        assert_eq!(result[1], (4.0, 180.0));
    }

    #[test]
    fn test_format_seconds() {
        assert_eq!(format_seconds(65.0), "01:05");
        assert_eq!(format_seconds(125.5), "02:05");
        assert_eq!(format_seconds(0.0), "00:00");
    }
}
