//! 判定系统
//!
//! 负责音游的判定逻辑、分数计算、连击系统

use serde::{Deserialize, Serialize};

/// 判定结果
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum JudgeResult {
    Perfect,
    Good,
    Bad,
    Miss,
}

impl JudgeResult {
    /// 获取显示文本
    pub fn display_text(&self) -> &'static str {
        match self {
            JudgeResult::Perfect => "PERFECT",
            JudgeResult::Good => "GOOD",
            JudgeResult::Bad => "BAD",
            JudgeResult::Miss => "MISS",
        }
    }

    /// 获取分数
    pub fn score(&self) -> u32 {
        match self {
            JudgeResult::Perfect => 100,
            JudgeResult::Good => 50,
            JudgeResult::Bad => 10,
            JudgeResult::Miss => 0,
        }
    }

    /// 获取颜色（RGB）
    pub fn color(&self) -> (u8, u8, u8) {
        match self {
            JudgeResult::Perfect => (50, 255, 100),  // 绿色
            JudgeResult::Good => (255, 220, 50),     // 黄色
            JudgeResult::Bad => (255, 80, 80),       // 红色
            JudgeResult::Miss => (150, 150, 150),    // 灰色
        }
    }
}

/// 判定配置
#[derive(Debug, Clone)]
pub struct JudgeConfig {
    /// PERFECT窗口（秒）
    pub perfect_window: f64,
    /// GOOD窗口（秒）
    pub good_window: f64,
    /// BAD窗口（秒）
    pub bad_window: f64,
    /// 连击奖励阈值
    pub combo_bonus_threshold: u32,
}

impl Default for JudgeConfig {
    fn default() -> Self {
        Self {
            perfect_window: 0.045,  // ±45ms
            good_window: 0.090,     // ±90ms
            bad_window: 0.135,      // ±135ms
            combo_bonus_threshold: 10,
        }
    }
}

/// 判定统计
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct JudgeStats {
    pub perfect: u32,
    pub good: u32,
    pub bad: u32,
    pub miss: u32,
}

impl JudgeStats {
    /// 总判定数
    pub fn total(&self) -> u32 {
        self.perfect + self.good + self.bad + self.miss
    }

    /// 命中数（不含MISS）
    pub fn hit_count(&self) -> u32 {
        self.perfect + self.good + self.bad
    }
}

/// 判定系统
#[derive(Debug)]
pub struct JudgeSystem {
    /// 配置
    config: JudgeConfig,
    /// 当前分数
    pub score: u32,
    /// 当前连击
    pub combo: u32,
    /// 最大连击
    pub max_combo: u32,
    /// 判定统计
    pub stats: JudgeStats,
    /// 箭头状态 (arrow_idx -> state, 0=未处理, 1=已命中, 2=已miss)
    arrow_states: std::collections::HashMap<usize, u8>,
}

impl Default for JudgeSystem {
    fn default() -> Self {
        Self::new()
    }
}

impl JudgeSystem {
    /// 创建新的判定系统
    pub fn new() -> Self {
        Self {
            config: JudgeConfig::default(),
            score: 0,
            combo: 0,
            max_combo: 0,
            stats: JudgeStats::default(),
            arrow_states: std::collections::HashMap::new(),
        }
    }

    /// 使用自定义配置创建
    pub fn with_config(config: JudgeConfig) -> Self {
        Self {
            config,
            ..Self::new()
        }
    }

    /// 重置所有统计
    pub fn reset(&mut self) {
        self.score = 0;
        self.combo = 0;
        self.max_combo = 0;
        self.stats = JudgeStats::default();
        self.arrow_states.clear();
    }

    /// 尝试判定指定轨道上的箭头
    ///
    /// # Arguments
    /// * `arrow_events` - 箭头事件列表
    /// * `track_idx` - 轨道索引
    /// * `current_sec` - 当前时间（秒）
    ///
    /// # Returns
    /// 判定结果，未命中返回None
    pub fn judge(
        &mut self,
        arrow_events: &[crate::models::ArrowEvent],
        track_idx: u8,
        current_sec: f64,
    ) -> Option<JudgeResult> {
        let mut best_idx: Option<usize> = None;
        let mut best_diff = f64::MAX;

        for (i, event) in arrow_events.iter().enumerate() {
            // 跳过不同轨道
            if event.track_idx != track_idx {
                continue;
            }
            // 跳过已处理的箭头
            if self.arrow_states.contains_key(&i) {
                continue;
            }

            let time_diff = (event.start_sec - current_sec).abs();

            // 在BAD窗口内才考虑
            if time_diff <= self.config.bad_window && time_diff < best_diff {
                best_diff = time_diff;
                best_idx = Some(i);
            }
        }

        let idx = best_idx?;

        // 判定结果
        let result = if best_diff <= self.config.perfect_window {
            JudgeResult::Perfect
        } else if best_diff <= self.config.good_window {
            JudgeResult::Good
        } else {
            JudgeResult::Bad
        };

        // 更新状态
        self.arrow_states.insert(idx, 1); // 已命中

        // 计算分数（含连击奖励）
        let mut score_add = result.score();
        if self.combo >= self.config.combo_bonus_threshold {
            score_add = (score_add as f32 * 1.1) as u32; // 10%加成
        }
        self.score += score_add;

        // 更新连击
        if result != JudgeResult::Bad {
            self.combo += 1;
            self.max_combo = self.max_combo.max(self.combo);
        } else {
            self.combo = 0;
        }

        // 更新统计
        match result {
            JudgeResult::Perfect => self.stats.perfect += 1,
            JudgeResult::Good => self.stats.good += 1,
            JudgeResult::Bad => self.stats.bad += 1,
            JudgeResult::Miss => self.stats.miss += 1,
        }

        Some(result)
    }

    /// 检测已错过判定窗口的箭头（MISS）
    ///
    /// # Arguments
    /// * `arrow_events` - 箭头事件列表
    /// * `current_sec` - 当前时间（秒）
    ///
    /// # Returns
    /// MISS的箭头索引列表
    pub fn check_missed(
        &mut self,
        arrow_events: &[crate::models::ArrowEvent],
        current_sec: f64,
    ) -> Vec<usize> {
        let mut missed = Vec::new();

        for (i, event) in arrow_events.iter().enumerate() {
            if self.arrow_states.contains_key(&i) {
                continue;
            }

            // 箭头已经离开BAD窗口
            if event.start_sec < current_sec - self.config.bad_window {
                self.arrow_states.insert(i, 2); // 已miss
                self.stats.miss += 1;
                self.combo = 0;
                missed.push(i);
            }
        }

        missed
    }

    /// 计算准确率
    ///
    /// # Returns
    /// 准确率 (0.0-1.0)
    pub fn get_accuracy(&self) -> f64 {
        let total = self.stats.total();
        if total == 0 {
            return 1.0;
        }

        // PERFECT=100%, GOOD=70%, BAD=30%, MISS=0%
        let weighted = self.stats.perfect * 100
            + self.stats.good * 70
            + self.stats.bad * 30;

        weighted as f64 / (total * 100) as f64
    }

    /// 获取评级
    ///
    /// # Returns
    /// 评级字符串 (S/AAA/AA/A/B/C/D/F)
    pub fn get_grade(&self) -> &'static str {
        let accuracy = self.get_accuracy();

        if accuracy >= 0.95 && self.stats.miss == 0 {
            "S"
        } else if accuracy >= 0.95 {
            "AAA"
        } else if accuracy >= 0.90 {
            "AA"
        } else if accuracy >= 0.80 {
            "A"
        } else if accuracy >= 0.70 {
            "B"
        } else if accuracy >= 0.60 {
            "C"
        } else if accuracy >= 0.50 {
            "D"
        } else {
            "F"
        }
    }

    /// 检查箭头是否已被处理
    pub fn is_arrow_processed(&self, arrow_idx: usize) -> bool {
        self.arrow_states.contains_key(&arrow_idx)
    }

    /// 获取箭头状态
    ///
    /// # Returns
    /// 0=未处理, 1=已命中, 2=已miss
    pub fn get_arrow_state(&self, arrow_idx: usize) -> u8 {
        self.arrow_states.get(&arrow_idx).copied().unwrap_or(0)
    }

    /// 获取当前分数
    pub fn get_score(&self) -> u32 {
        self.score
    }

    /// 获取当前连击
    pub fn get_combo(&self) -> u32 {
        self.combo
    }

    /// 获取最大连击
    pub fn get_max_combo(&self) -> u32 {
        self.max_combo
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_judge_result() {
        assert_eq!(JudgeResult::Perfect.score(), 100);
        assert_eq!(JudgeResult::Good.score(), 50);
        assert_eq!(JudgeResult::Bad.score(), 10);
        assert_eq!(JudgeResult::Miss.score(), 0);
    }

    #[test]
    fn test_judge_system() {
        let mut judge = JudgeSystem::new();

        let arrows = vec![
            crate::models::ArrowEvent {
                track_idx: 0,
                start_sec: 1.0,
                end_sec: 1.0,
                arrow_type: 0,
            },
        ];

        // 测试PERFECT判定
        let result = judge.judge(&arrows, 0, 1.02);
        assert_eq!(result, Some(JudgeResult::Perfect));

        judge.reset();

        // 测试GOOD判定
        let result = judge.judge(&arrows, 0, 1.07);
        assert_eq!(result, Some(JudgeResult::Good));
    }
}
