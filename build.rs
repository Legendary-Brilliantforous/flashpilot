// Copy the bundled EDL payloads next to the built binary so `cargo run`,
// `cargo build --release`, and the in-source GUI (which uses
// target/release/flashpilot-bridge) resolve them through
// `<exe_dir>/payloads/<engine>`.
//
//   payloads/mtk   MediaTek BROM payloads (GPLv3)
//   payloads/qcom  Qualcomm firehose programmers (+ index.json)
//
// The .deb installs its own copy to /usr/lib/flashpilot/payloads/<engine>
// (see packaging/build-deb.sh), and release binaries never bake the build
// machine's path in.
use std::path::{Path, PathBuf};

fn main() {
    for engine in ["mtk", "qcom"] {
        println!("cargo:rerun-if-changed=payloads/{engine}");
        copy_payloads(Path::new("payloads").join(engine).as_path());
    }
}

fn copy_payloads(src: &Path) {
    let Ok(out_dir) = std::env::var("OUT_DIR") else {
        return;
    };
    // OUT_DIR = target/<profile>/build/<pkg>-<hash>/out
    let Some(profile_dir) = Path::new(&out_dir).ancestors().nth(3) else {
        return;
    };

    if !src.is_dir() {
        return;
    }
    let Some(name) = src.file_name() else {
        return;
    };
    let dst: PathBuf = profile_dir.join("payloads").join(name);
    if std::fs::create_dir_all(&dst).is_err() {
        return;
    }

    let Ok(entries) = std::fs::read_dir(src) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_file() {
            let _ = std::fs::copy(&path, dst.join(entry.file_name()));
        }
    }
}
