use std::process::Command;
use crate::error::{Result, BridgeError};

fn adb_output() -> Result<std::process::Output> {
    // If a stale adb server is occupying 5037, start the daemon explicitly
    // (kills/restarts any conflicting server) so `adb devices` doesn't fail.
    match Command::new("adb").arg("start-server").output() {
        Ok(o) if !o.status.success() => {
            // still proceed: a fresh `adb devices` may work anyway
        }
        Err(e) => return Err(BridgeError::InvalidArgument(format!("adb not found: {e}"))),
        _ => {}
    }
    Command::new("adb")
        .arg("devices")
        .arg("-l")
        .output()
        .map_err(|e| BridgeError::InvalidArgument(format!("adb not found: {e}")))
}

pub fn devices_json() -> Result<String> {
    let out = adb_output()?;

    if !out.status.success() {
        return Err(BridgeError::InvalidArgument(String::from_utf8_lossy(&out.stderr).trim().to_string()));
    }

    let lines: Vec<String> = String::from_utf8_lossy(&out.stdout)
        .lines()
        .skip(1)
        .filter(|l| !l.trim().is_empty())
        .map(|l| l.to_string())
        .collect();

    let json = serde_json::to_string(&lines).map_err(|e| BridgeError::Config(crate::error::ConfigError::ParseError(e.to_string())))?;
    Ok(json)
}

pub fn shell(cmd: &str) -> Result<String> {
    let out = Command::new("adb")
        .arg("shell")
        .arg(cmd)
        .output()
        .map_err(|e| BridgeError::InvalidArgument(format!("adb not found: {e}")))?;

    if !out.status.success() {
        let err = String::from_utf8_lossy(&out.stderr);
        if !err.trim().is_empty() {
            return Err(BridgeError::InvalidArgument(err.trim().to_string()));
        }
    }
    Ok(String::from_utf8_lossy(&out.stdout).to_string())
}
