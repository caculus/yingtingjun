//! Thin CLI wrapper around speakrs for voice2txt.
//!
//! Usage:
//!   speakrs_diarize [--mode coreml|coreml-fast|cpu] [--models-dir DIR] <audio.wav>
//!
//! Prints JSON to stdout:
//!   {"segments":[{"start":0.0,"end":1.2,"speaker":"SPEAKER_00"}, ...], "mode":"coreml"}

use serde::Serialize;
use speakrs::{ExecutionMode, OwnedDiarizationPipeline};
use std::env;
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process;

#[derive(Serialize)]
struct SegmentOut {
    start: f64,
    end: f64,
    speaker: String,
}

#[derive(Serialize)]
struct Output {
    mode: String,
    segments: Vec<SegmentOut>,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("speakrs_diarize error: {err}");
        process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut mode_name = default_mode_name();
    let mut models_dir: Option<PathBuf> = None;
    let mut audio_path: Option<PathBuf> = None;

    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--mode" => {
                i += 1;
                mode_name = args
                    .get(i)
                    .cloned()
                    .ok_or("--mode requires a value (coreml|coreml-fast|cpu)")?;
            }
            "--models-dir" => {
                i += 1;
                let dir = args
                    .get(i)
                    .cloned()
                    .ok_or("--models-dir requires a path")?;
                models_dir = Some(PathBuf::from(dir));
            }
            "-h" | "--help" => {
                print_usage();
                return Ok(());
            }
            other if other.starts_with('-') => {
                return Err(format!("unknown flag: {other}").into());
            }
            other => {
                if audio_path.is_some() {
                    return Err("only one audio path is allowed".into());
                }
                audio_path = Some(PathBuf::from(other));
            }
        }
        i += 1;
    }

    let audio_path = audio_path.ok_or_else(|| {
        print_usage();
        "missing <audio.wav>".to_string()
    })?;

    let mode = parse_mode(&mode_name)?;
    eprintln!(
        "speakrs_diarize: loading pipeline mode={mode_name} audio={}",
        audio_path.display()
    );

    let audio = load_wav_samples(&audio_path)?;
    let mut pipeline = match models_dir {
        Some(dir) => {
            eprintln!("speakrs_diarize: models from {}", dir.display());
            OwnedDiarizationPipeline::from_dir(&dir, mode)?
        }
        None => {
            eprintln!("speakrs_diarize: downloading / caching models via from_pretrained …");
            OwnedDiarizationPipeline::from_pretrained(mode)?
        }
    };

    eprintln!("speakrs_diarize: running diarization ({} samples) …", audio.len());
    let result = pipeline.run(&audio)?;

    let mut exclusive = result.discrete_diarization.clone();
    exclusive.make_exclusive();
    let segments = exclusive
        .to_segments()
        .into_iter()
        .map(|s| SegmentOut {
            start: s.start,
            end: s.end,
            speaker: s.speaker,
        })
        .collect::<Vec<_>>();

    eprintln!(
        "speakrs_diarize: done — {} exclusive segments",
        segments.len()
    );

    let out = Output {
        mode: mode_name,
        segments,
    };
    let json = serde_json::to_string(&out)?;
    let mut stdout = io::stdout().lock();
    stdout.write_all(json.as_bytes())?;
    stdout.write_all(b"\n")?;
    Ok(())
}

fn default_mode_name() -> String {
    if cfg!(target_os = "macos") {
        "coreml".to_string()
    } else {
        "cpu".to_string()
    }
}

fn parse_mode(name: &str) -> Result<ExecutionMode, String> {
    match name {
        "coreml" => Ok(ExecutionMode::CoreMl),
        "coreml-fast" => Ok(ExecutionMode::CoreMlFast),
        "cpu" => Ok(ExecutionMode::Cpu),
        other => Err(format!(
            "unknown mode '{other}' (expected coreml|coreml-fast|cpu)"
        )),
    }
}

fn print_usage() {
    eprintln!(
        "Usage: speakrs_diarize [--mode coreml|coreml-fast|cpu] [--models-dir DIR] <audio.wav>"
    );
}

fn load_wav_samples(path: &Path) -> Result<Vec<f32>, Box<dyn std::error::Error + Send + Sync>> {
    let data = fs::read(path)?;
    if data.len() < 44 {
        return Err("WAV file too short".into());
    }

    let channels = u16::from_le_bytes(data[22..24].try_into()?);
    let sample_rate = u32::from_le_bytes(data[24..28].try_into()?);
    let bits_per_sample = u16::from_le_bytes(data[34..36].try_into()?);

    if channels != 1 {
        return Err(format!("expected mono WAV, got {channels} channels").into());
    }
    if sample_rate != 16_000 {
        return Err(format!("expected 16kHz WAV, got {sample_rate}Hz").into());
    }
    if bits_per_sample != 16 {
        return Err(format!("expected 16-bit PCM WAV, got {bits_per_sample}-bit").into());
    }

    let mut pos = 12usize;
    while pos + 8 <= data.len() {
        let chunk_id = &data[pos..pos + 4];
        let chunk_size = u32::from_le_bytes(data[pos + 4..pos + 8].try_into()?) as usize;
        let data_start = pos + 8;
        let data_end = data_start.saturating_add(chunk_size);
        if data_end > data.len() {
            break;
        }
        if chunk_id == b"data" {
            let samples = data[data_start..data_end]
                .chunks_exact(2)
                .map(|bytes| i16::from_le_bytes([bytes[0], bytes[1]]) as f32 / 32768.0)
                .collect();
            return Ok(samples);
        }
        // RIFF chunks are word-aligned.
        pos = data_end + (chunk_size % 2);
    }

    Err("no data chunk found in WAV".into())
}
