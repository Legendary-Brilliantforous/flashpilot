mod adb;
mod at;
mod bulk;
mod config;
mod error;
mod hid;
mod mtk;
mod mtk_da;
mod mtk_exploit;
mod mtk_sla;
mod mtk_sla_keys;
mod mtp;
mod odin;
mod qualcomm;
mod spd;
mod usb;
mod util;

use std::process::exit;

const SAMSUNG_VID: u16 = 0x04e8;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: flashpilot-bridge <command> [args...]");
        eprintln!("commands:");
        eprintln!("  detect                 list USB devices (all + Samsung filter)");
        eprintln!("  hid-list               list HID interfaces on Samsung devices");
        eprintln!("  hid-open <path> <out>  send hex bytes <out> to HID report, print response hex");
        eprintln!("  bulk-list              list bulk endpoints on Samsung devices");
        eprintln!("  bulk-send <t> <hex> [n] raw bulk write/read on a Samsung device");
        eprintln!("  bulk-session <t> <cmd>...  persistent session: w<hex> write, r<n> read");
        eprintln!("  mtk-detect             detect MediaTek BROM/preloader/DA devices");
        eprintln!("  mtk-da-upload <t> <da> upload Download Agent to device in BROM/preloader");
        eprintln!("  mtk-scatter <file>     parse and display scatter file info");
        eprintln!("  mtk-scatter-gpt <t> <da> <out>  generate a scatter file from the device GPT");
        eprintln!("  mtk-flash <t> <da> <scatter> <fw_dir>  flash firmware from scatter");
        eprintln!("  mtk-backup <t> <da> <scatter> <out_dir>  backup partitions");
        eprintln!("  mtk-frp <t> <da> <scatter>  FRP bypass (wipe frp/nvdata)");
        eprintln!("  mtk-adb-enable <t> <da> <scatter>  attempt ADB enable");
        eprintln!("  mtk-reboot <t> <da> <mode>  reboot device (0=normal,1=bl,2=rec,3=fastboot,4=brom)");
        eprintln!("  mtk-factory <t>        enter factory/dealer mode");
        eprintln!("  mtk-emergency <t>      detect emergency/download mode devices");
        eprintln!("  mtk-bypass <t> <da> <mode> [scatter] [skip_auth]  unified bypass (standard|brom_exploit|da_auth_bypass|factory|emergency|sla_bypass)");
        eprintln!("  mtk-dealer <t> <da>    dealer mode (auth, unlock, FRP erase, secure config)");
        eprintln!("  mtk-emergency-mode <t> <da>  emergency mode (full partition access)");
        eprintln!("  mtk-exploit <t> <type> [payload]  BROM exploit (mtk_bypass|kamakiri2|dump_preloader|patch_da|custom)");
        eprintln!("  mtk-gpt <t> <da>       list device GPT partition table by name (no scatter)");
        eprintln!("  mtk-flash-part <t> <da> <part=file>...  write partitions by name (no scatter)");
        eprintln!("  mtk-read-part <t> <da> <part> <out>      read one partition by name (no scatter)");
        eprintln!("  mtk-frp-gpt <t> <da>  FRP bypass resolving lock partitions from device GPT (no scatter)");
        eprintln!("  qcom-detect            detect Qualcomm EDL devices");
        eprintln!("  spd-detect             detect Spreadtrum/UNISOC download devices");
        eprintln!("  spd-info <t>           full SPD device info (read-only, safe)");
        eprintln!("  spd-format <t> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr]  password wipe / factory format (no firmware flash)");
        eprintln!("  spd-frp <t> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr]  erase FRP lock partitions");
        eprintln!("  spd-backup <t> <fdl1> <fdl1_addr> <fdl2> <fdl2_addr> <out_dir>  list partitions + dump");
        eprintln!("  spd-partitions <t> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr]  list Android partition table");
        eprintln!("  spd-flash <t> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr] <part=file>...  write partitions/regions");
        eprintln!("  spd-reset <t>          reset device to normal mode");        eprintln!("  qcom-sahara <t>        handshake with Qualcomm EDL device (Sahara)");
        eprintln!("  qcom-firehose <t> <prog>  start Firehose session with programmer");
        eprintln!("  qcom-flash <t> <prog> <xml> <fw_dir>  flash via Firehose rawprogram.xml");
        eprintln!("  qcom-backup <t> <prog> <out>  backup partitions via Firehose");
        eprintln!("  qcom-partitions <t>    get partition table via Firehose");
        eprintln!("  qcom-reboot <t> <mode> reboot device (normal|edl|recovery|fastboot)");
        eprintln!("  qcom-info <t>          get device info via Sahara");
        eprintln!("  adb-devices            print `adb devices -l` output as JSON");
        eprintln!("  adb-shell <cmd>        run `adb shell <cmd>`, print stdout");
        eprintln!("  usb-config <t> <idx>   set USB configuration <idx> on target");
        eprintln!("  usb-detach-kernel <t>  detach kernel drivers (cdc_acm) from all interfaces");
        eprintln!("  at-send <t> <cmd> [ms]  send AT command over CDC ACM, read reply");
        eprintln!("  mtp-info <t> [ms]      MTP GetDeviceInfo: ops/events/properties supported");
        eprintln!("  odin-connect <t>       open Odin session to Samsung device");
        eprintln!("  odin-agent <t>         long-lived Odin session (JSON lines on stdin)");
        eprintln!("  odin-pit <t> [out]     read PIT from Samsung device");
        eprintln!("  odin-pit-mtk <t> [out] read PIT from Samsung MTK device");
        eprintln!("  odin-info <t> <pit>    show partition info from PIT");
        eprintln!("  odin-model <t>         get device model string");
        eprintln!("  odin-flash <t> <pit> <partition> <image>  flash single partition");
        eprintln!("  odin-send-pit <t> <pit>  send PIT to device");
        eprintln!("  odin-flash-multi <t> <pit> <reboot> <part=file>...  flash multiple partitions");
        exit(2);
    }

    let result = match args[1].as_str() {
        "detect" => usb::detect(Some(SAMSUNG_VID)),
        "detect-all" => usb::detect(None),
        "hid-list" => hid::list_samsung_hid(),
        "hid-open" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge hid-open <path> <hex>");
                exit(2);
            }
            hid::open_and_send(&args[2], &args[3])
        }
        "bulk-list" => bulk::list_bulk_targets(),
        "mtk-detect" => mtk::detect_mtk(),
        "mtk-da-upload" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge mtk-da-upload <target> <da_file>");
                exit(2);
            }
            mtk_da::mtk_da_upload(&args[2], &args[3])
        }
        "mtk-scatter" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge mtk-scatter <scatter_file>");
                exit(2);
            }
            mtk_da::mtk_scatter_parse(&args[2])
        }
        "mtk-flash" => {
            if args.len() < 6 {
                eprintln!("usage: flashpilot-bridge mtk-flash <target> <da_file> <scatter_file> <firmware_dir>");
                exit(2);
            }
            mtk_da::mtk_flash_firmware(&args[2], &args[3], &args[4], &args[5])
        }
        "mtk-backup" => {
            if args.len() < 5 {
                eprintln!("usage: flashpilot-bridge mtk-backup <target> <da_file> <scatter_file> <out_dir>");
                exit(2);
            }
            mtk_da::mtk_backup(&args[2], &args[3], &args[4], &args[5])
        }
        "mtk-gpt" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge mtk-gpt <target> <da_file>");
                exit(2);
            }
            mtk_da::mtk_gpt_cli(&args[2], &args[3])
        }
        "mtk-scatter-gpt" => {
            if args.len() < 5 {
                eprintln!("usage: flashpilot-bridge mtk-scatter-gpt <target> <da_file> <out_file>");
                exit(2);
            }
            mtk_da::mtk_scatter_gpt_cli(&args[2], &args[3], &args[4])
        }
        "mtk-flash-part" => {
            // mtk-flash-part <target> <da_file> <partition=file>...
            if args.len() < 5 {
                eprintln!("usage: flashpilot-bridge mtk-flash-part <target> <da_file> <partition=file>...");
                exit(2);
            }
            let target = args[2].clone();
            let da = args[3].clone();
            let mut entries = Vec::new();
            for e in &args[4..] {
                if let Some((part, file)) = e.split_once('=') {
                    entries.push((part.to_string(), file.to_string()));
                } else {
                    eprintln!("usage: entry must be partition=file, got '{e}'");
                    exit(2);
                }
            }
            mtk_da::mtk_flash_part_cli(&target, &da, &entries)
        }
        "mtk-read-part" => {
            if args.len() < 6 {
                eprintln!("usage: flashpilot-bridge mtk-read-part <target> <da_file> <partition> <out_file>");
                exit(2);
            }
            mtk_da::mtk_read_part_cli(&args[2], &args[3], &args[4], &args[5])
        }
        "mtk-frp" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge mtk-frp <target> <da_file> <scatter_file>");
                exit(2);
            }
            mtk_da::mtk_frp_bypass(&args[2], &args[3], &args[4])
        }
        "mtk-frp-gpt" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge mtk-frp-gpt <target> <da_file>");
                exit(2);
            }
            mtk_da::mtk_frp_bypass_gpt(&args[2], &args[3])
        }
        "mtk-adb-enable" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge mtk-adb-enable <target> <da_file> <scatter_file>");
                exit(2);
            }
            mtk_da::mtk_adb_enable(&args[2], &args[3], &args[4])
        }
        "mtk-reboot" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge mtk-reboot <target> <da_file> <mode>");
                exit(2);
            }
            let mode: u8 = args[4].parse().unwrap_or(0);
            mtk_da::mtk_reboot(&args[2], &args[3], mode)
        }
        "mtk-factory" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge mtk-factory <target>");
                exit(2);
            }
            mtk_da::mtk_enter_factory_mode(&args[2])
        }
        "mtk-emergency" => {
            mtk_da::mtk_detect_emergency_mode()
        }
        "mtk-bypass" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge mtk-bypass <target> <da_file> <mode> [scatter_file] [skip_auth]");
                eprintln!("  modes: standard, brom_exploit, da_auth_bypass, factory, emergency, sla_bypass");
                exit(2);
            }
            let scatter = args.get(5).map(|s| s.as_str());
            let skip_auth = args.get(6).map(|s| s == "1").unwrap_or(false);
            mtk_da::mtk_bypass_cli(&args[2], &args[3], &args[4], scatter, skip_auth)
        }
        "mtk-dealer" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge mtk-dealer <target> <da_file>");
                exit(2);
            }
            mtk_da::mtk_dealer_mode(&args[2], &args[3])
        }
        "mtk-emergency-mode" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge mtk-emergency-mode <target> <da_file>");
                exit(2);
            }
            mtk_da::mtk_emergency_mode(&args[2], &args[3])
        }
        "mtk-exploit" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge mtk-exploit <target> <type> [payload_file]");
                eprintln!("  types:");
                eprintln!("    mtk_bypass     handshake + kamakiri2 + dump+patch preloader (recommended)");
                eprintln!("    kamakiri2      run the CVE-2020-11152 linecoding exploit only");
                eprintln!("    dump_preloader handshake + dump preloader from RAM");
                eprintln!("    patch_da       patch a DA/preloader file in place (payload_file)");
                eprintln!("                   optional 3rd arg: da1 (default) | da2 | parse");
                eprintln!("    custom         upload a custom payload via kamakiri2 (payload_file)");
                exit(2);
            }
            let payload = args.get(4).map(|s| s.as_str());
            let payload2 = args.get(5).map(|s| s.as_str());
            match args[3].as_str() {
                "patch_da" => {
                    let err = |e: String| {
                        Err(crate::error::BridgeError::InvalidArgument(e))
                    };
                    match payload {
                        Some(path) => match std::fs::read(path) {
                            Ok(data) => {
                                let mut v = data;
                                let mode = payload2.unwrap_or("da1");
                                if mode == "parse" {
                                    let (addr, _) = mtk_exploit::parse_preloader(&v);
                                    println!(
                                        "{}: preloader header -> DA addr 0x{:x}, {} bytes",
                                        path,
                                        addr,
                                        v.len()
                                    );
                                    Ok("{}".to_string())
                                } else {
                                    let n = match mode {
                                        "da2" => mtk_exploit::patch_preloader_security_da2(&mut v),
                                        _ => mtk_exploit::patch_preloader_security_da1(&mut v),
                                    };
                                    let patched = format!("{path}.patched");
                                    match std::fs::write(&patched, &v) {
                                        Ok(()) => {
                                            println!(
                                                "{}: applied {n} patch(es) ({mode}) -> {} ({} bytes)",
                                                path,
                                                patched,
                                                v.len()
                                            );
                                            Ok("{}".to_string())
                                        }
                                        Err(e) => err(format!("write {patched}: {e}")),
                                    }
                                }
                            }
                            Err(e) => err(format!("read {path}: {e}")),
                        },
                        None => err("patch_da requires a payload_file".to_string()),
                    }
                }
                "kamakiri2" | "custom" => {
                    match payload {
                        Some(p) => mtk_exploit::brom_run_payload(&args[2], p),
                        None => Err(crate::error::BridgeError::InvalidArgument(
                            "kamakiri2/custom requires a payload_file".to_string(),
                        )),
                    }
                }
                _ => mtk_exploit::brom_bypass(&args[2]),
            }
        }
        "qcom-detect" => {
            qualcomm::qcom_detect()
        }
        "qcom-sahara" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge qcom-sahara <target>");
                exit(2);
            }
            qualcomm::qcom_sahara_handshake(&args[2])
        }
        "qcom-firehose" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge qcom-firehose <target> <programmer>");
                exit(2);
            }
            qualcomm::qcom_firehose_start(&args[2], &args[3])
        }
        "qcom-flash" => {
            if args.len() < 5 {
                eprintln!("usage: flashpilot-bridge qcom-flash <target> <programmer> <rawprogram.xml> <fw_dir>");
                exit(2);
            }
            qualcomm::qcom_flash_firmware(&args[2], &args[3], &args[4], &args[5])
        }
        "qcom-backup" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge qcom-backup <target> <programmer> <out_dir>");
                exit(2);
            }
            qualcomm::qcom_backup(&args[2], &args[3], &args[4])
        }
        "qcom-partitions" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge qcom-partitions <target>");
                exit(2);
            }
            qualcomm::qcom_partitions(&args[2])
        }
        "qcom-reboot" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge qcom-reboot <target> <mode>");
                exit(2);
            }
            qualcomm::qcom_reboot(&args[2], &args[3])
        }
        "qcom-info" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge qcom-info <target>");
                exit(2);
            }
            qualcomm::qcom_device_info(&args[2])
        }
        "qcom-frp-reset" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge qcom-frp-reset <target>");
                exit(2);
            }
            qualcomm::qcom_frp_reset(&args[2])
        }
        "spd-detect" => spd::spd_detect_cli(),
        "spd-info" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge spd-info <target>");
                exit(2);
            }
            spd::spd_info_cli(&args[2])
        }
        "spd-format" => {
            if args.len() < 5 {
                eprintln!("usage: flashpilot-bridge spd-format <target> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr]");
                exit(2);
            }
            let fdl1_addr = u32::from_str_radix(&args[4].trim_start_matches("0x"), 16)
                .unwrap_or_else(|_| {
                    eprintln!("invalid FDL1 address '{}'", args[4]);
                    exit(2);
                });
            let fdl2 = args.get(5).map(|s| s.as_str());
            let fdl2_addr = args.get(6).map(|s| {
                u32::from_str_radix(s.trim_start_matches("0x"), 16).unwrap_or(0)
            });
            spd::spd_format_cli(&args[2], &args[3], fdl1_addr, fdl2, fdl2_addr)
        }
        "spd-frp" => {
            if args.len() < 5 {
                eprintln!("usage: flashpilot-bridge spd-frp <target> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr]");
                exit(2);
            }
            let fdl1_addr = u32::from_str_radix(&args[4].trim_start_matches("0x"), 16)
                .unwrap_or_else(|_| {
                    eprintln!("invalid FDL1 address '{}'", args[4]);
                    exit(2);
                });
            let fdl2 = args.get(5).map(|s| s.as_str());
            let fdl2_addr = args.get(6).map(|s| {
                u32::from_str_radix(s.trim_start_matches("0x"), 16).unwrap_or(0)
            });
            spd::spd_frp_cli(&args[2], &args[3], fdl1_addr, fdl2, fdl2_addr)
        }
        "spd-backup" => {
            if args.len() < 8 {
                eprintln!("usage: flashpilot-bridge spd-backup <target> <fdl1> <fdl1_addr> <fdl2> <fdl2_addr> <out_dir>");
                exit(2);
            }
            let fdl1_addr = u32::from_str_radix(&args[4].trim_start_matches("0x"), 16).unwrap_or(0);
            let fdl2_addr = u32::from_str_radix(&args[6].trim_start_matches("0x"), 16).unwrap_or(0);
            spd::spd_backup_cli(&args[2], &args[3], fdl1_addr, &args[5], fdl2_addr, &args[7])
        }
        "spd-partitions" => {
            if args.len() < 7 {
                eprintln!("usage: flashpilot-bridge spd-partitions <target> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr]");
                exit(2);
            }
            let target = args[2].clone();
            let fdl1 = args[3].clone();
            let fdl1_addr = u32::from_str_radix(&args[4].trim_start_matches("0x"), 16).unwrap_or(0);
            let (fdl2, fdl2_addr) = if args.len() >= 7 && args[5] != "none" {
                let a = u32::from_str_radix(&args[6].trim_start_matches("0x"), 16).unwrap_or(0);
                (Some(args[5].clone()), Some(a))
            } else {
                (None, None)
            };
            spd::spd_partitions_cli(&target, &fdl1, fdl1_addr, fdl2.as_deref(), fdl2_addr)
        }
        "spd-reset" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge spd-reset <target>");
                exit(2);
            }
            spd::spd_reset_cli(&args[2])
        }
        "spd-flash" => {
            // spd-flash <target> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr] <part=file>...
            if args.len() < 6 {
                eprintln!("usage: flashpilot-bridge spd-flash <target> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr] <part=file>...");
                exit(2);
            }
            let target = args[2].clone();
            let fdl1 = args[3].clone();
            let fdl1_addr = u32::from_str_radix(&args[4].trim_start_matches("0x"), 16).unwrap_or(0);
            let mut rest = args[5..].to_vec();
            // Optional [fdl2] [fdl2_addr] pair: the fdl2 value is present and
            // not a partition=file entry, and (if the next token parses as hex
            // or the token is "none") we treat it as the fdl2 path.
            let mut fdl2: Option<String> = None;
            let mut fdl2_addr: Option<u32> = None;
            if !rest.is_empty()
                && !rest[0].contains('=')
                && rest[0] != "none"
            {
                fdl2 = Some(rest.remove(0));
                if !rest.is_empty() && !rest[0].contains('=') {
                    fdl2_addr = Some(u32::from_str_radix(&rest[0].trim_start_matches("0x"), 16).unwrap_or(0));
                    rest.remove(0);
                }
            }
            let mut entries: Vec<(String, String)> = Vec::new();
            for tok in &rest {
                if let Some(eq) = tok.find('=') {
                    entries.push((tok[..eq].to_string(), tok[eq + 1..].to_string()));
                } else {
                    eprintln!("bad entry '{tok}' (expected partition=file)");
                    exit(2);
                }
            }
            spd::spd_flash_cli(&target, &fdl1, fdl1_addr, fdl2.as_deref(), fdl2_addr, &entries)
        }
        "adb-devices" => adb::devices_json(),
        "adb-shell" => {
            let cmd = args[2..].join(" ");
            adb::shell(&cmd)
        }
        "usb-config" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge usb-config <target> <config_index>");
                exit(2);
            }
            let idx: usize = match args[3].parse() {
                Ok(v) => v,
                Err(_) => {
                    eprintln!("bad config index: {}", args[3]);
                    exit(2);
                }
            };
            usb::set_config(&args[2], idx)
        }
        "usb-detach-kernel" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge usb-detach-kernel <target>");
                exit(2);
            }
            usb::detach_kernel_drivers(&args[2])
        }
        "at-send" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge at-send <target> <cmd> [timeout_ms]");
                exit(2);
            }
            let timeout_ms = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(3000);
            at::at_send(&args[2], &args[3], timeout_ms)
        }
        "mtp-info" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge mtp-info <target> [timeout_ms]");
                exit(2);
            }
            let timeout_ms = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(6000);
            mtp::mtp_info(&args[2], timeout_ms)
        }
        "odin-connect" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge odin-connect <target>");
                exit(2);
            }
            odin::odin_connect(&args[2])
        }
        "odin-pit" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge odin-pit <target> [outfile]");
                exit(2);
            }
            odin::odin_pit(&args[2], args.get(3).map(|s| s.as_str()))
        }
        "odin-pit-mtk" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge odin-pit-mtk <target> [outfile]");
                exit(2);
            }
            odin::odin_pit_mtk(&args[2], args.get(3).map(|s| s.as_str()))
        }
        "odin-info" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge odin-info <target> <pit_file>");
                exit(2);
            }
            odin::odin_info(&args[2], &args[3])
        }
        "odin-model" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge odin-model <target>");
                exit(2);
            }
            odin::odin_model(&args[2])
        }
        "odin-flash" => {
            if args.len() < 6 {
                eprintln!("usage: flashpilot-bridge odin-flash <target> <pit_file> <partition> <image_file>");
                exit(2);
            }
            let image = &args[5];
            odin::odin_flash_partition(&args[2], &args[3], &args[4], image)
        }
        "odin-send-pit" => {
            if args.len() < 4 {
                eprintln!("usage: flashpilot-bridge odin-send-pit <target> <pit_file>");
                exit(2);
            }
            odin::odin_send_pit(&args[2], &args[3])
        }
        "odin-agent" => {
            if args.len() < 3 {
                eprintln!("usage: flashpilot-bridge odin-agent <target>");
                exit(2);
            }
            odin::odin_agent(&args[2])
        }
        "odin-flash-multi" => {
            if args.len() < 6 {
                eprintln!("usage: flashpilot-bridge odin-flash-multi <target> <pit_file> <reboot:0|1> <part=file> [part=file ...]");
                exit(2);
            }
            let reboot = args[4] == "1";
            let mut files: Vec<(String, String)> = Vec::new();
            for spec in &args[5..] {
                match spec.split_once('=') {
                    Some((p, f)) => files.push((p.to_string(), f.to_string())),
                    None => {
                        eprintln!("error: expected partition=file, got '{spec}'");
                        exit(2);
                    }
                }
            }
            let refs: Vec<(&str, &str)> = files
                .iter()
                .map(|(p, f)| (p.as_str(), f.as_str()))
                .collect();
            odin::odin_flash_multi(&args[2], &args[3], &refs, reboot)
        }
        other => {
            eprintln!("unknown command: {other}");
            exit(2);
        }
    };

    match result {
        Ok(out) => println!("{out}"),
        Err(e) => {
            eprintln!("error: {e}");
            exit(1);
        }
    }
}