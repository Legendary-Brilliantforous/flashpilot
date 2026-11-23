/*
 * Protocol data for the interactive handshake panel.
 *
 * Every packet code, USB id and command name below is taken from the Rust
 * core in this repository — src/sam_download.rs, src/mtk.rs, src/qualcomm/
 * and src/spd.rs. Nothing here is invented for marketing; it is what the
 * bridge actually puts on the wire.
 */

export type ProtocolStep = {
  /** What the step does, in the technician's words. */
  title: string
  /** Wire-level detail — command codes and constants from the Rust core. */
  wire: string
  /** One line explaining why the step exists. */
  note: string
}

export type Protocol = {
  id: string
  /** Vendor label used on the tab. */
  vendor: string
  /** Protocol name. */
  protocol: string
  /** USB vendor:product the phone enumerates as in this mode. */
  usbId: string
  /** How a technician gets the phone into this mode. */
  entry: string
  /** Where the implementation lives in the Rust core. */
  source: string
  /** The bridge command that opens this mode. */
  cli: string
  /** The handshake, in order. */
  steps: ProtocolStep[]
}

export const PROTOCOLS: Protocol[] = [
  {
    id: 'samsung',
    vendor: 'Samsung',
    protocol: 'Odin download mode',
    usbId: '04e8:685d',
    entry: 'Download mode — Volume Down + Home on older models, Volume Down on newer ones.',
    source: 'src/sam_download.rs',
    cli: './target/release/flashpilot-bridge odin-info 04e8:xxxx',
    steps: [
      {
        title: 'Begin session',
        wire: '0x64 / 0x00',
        note: 'Negotiates the protocol version. Modern devices move to 1 MiB frames; legacy ones stay on 128 KiB.',
      },
      {
        title: 'Query the device type',
        wire: '0x64 / 0x01',
        note: 'Returns the model string — SM-A145F and friends.',
      },
      {
        title: 'Dump device info',
        wire: '0x69',
        note: 'Model, serial, region and carrier, read back in 512-byte blocks.',
      },
      {
        title: 'Read the partition table',
        wire: '0x65 / 0x01',
        note: 'Pulls the PIT so writes match the phone instead of a guessed layout.',
      },
      {
        title: 'Request the file flash',
        wire: '0x64 / 0x02 then 0x66 / 0x00',
        note: 'Declares the byte count, then opens the partition write.',
      },
      {
        title: 'End the session',
        wire: '0x67',
        note: 'Commits the write with staged delays, 500 ms up to 6 s, so the phone survives it.',
      },
    ],
  },
  {
    id: 'mediatek',
    vendor: 'MediaTek',
    protocol: 'BROM / preloader / download agent',
    usbId: '0e8d:0003 and 0e8d:2000',
    entry: 'Boot ROM mode — the phone hands control to the preloader, then to the download agent.',
    source: 'src/mtk.rs and src/mtk_da.rs',
    cli: './target/release/flashpilot-bridge mtk-detect',
    steps: [
      {
        title: 'Sync the boot ROM',
        wire: 'a0 0a 50 05',
        note: 'Brings the ROM out of its idle state and into command mode.',
      },
      {
        title: 'Read hardware and software version',
        wire: '0xfc',
        note: 'Eight bytes back: hardware sub-code, hardware version, software version.',
      },
      {
        title: 'Read memory',
        wire: '0xd0 and 0xd1',
        note: 'READ16 and READ32, each echoing the command, address and count before the payload.',
      },
      {
        title: 'Jump to the download agent',
        wire: '0xd5',
        note: 'Uploads the DA and jumps to it. A keep-alive packet goes out every 0x2000 bytes.',
      },
      {
        title: 'Run the DA session',
        wire: 'scatter and GPT',
        note: 'The download agent takes over: partition writes, backups, and real percentage progress.',
      },
    ],
  },
  {
    id: 'qualcomm',
    vendor: 'Qualcomm',
    protocol: 'EDL — Sahara and Firehose',
    usbId: '05c6:9008',
    entry: 'Emergency download mode — both volume keys on plug-in, or a test point on models without the combo.',
    source: 'src/qualcomm/sahara.rs and src/qualcomm/firehose.rs',
    cli: './target/release/flashpilot-bridge qcom-detect',
    steps: [
      {
        title: 'Say hello',
        wire: '0x01 / 0x02',
        note: 'The Sahara hello handshake answers with the memory map and device info.',
      },
      {
        title: 'Read memory',
        wire: '0x0b',
        note: 'Reads device memory straight over Sahara, before any programmer is loaded.',
      },
      {
        title: 'Upload the programmer',
        wire: '0x05 / 0x04 then 0x11',
        note: 'Streams the Firehose programmer, then switches the device to streaming mode.',
      },
      {
        title: 'Configure the target',
        wire: '<configure>',
        note: 'Firehose XML: which target, which memory — eMMC or UFS.',
      },
      {
        title: 'Program, erase, list partitions',
        wire: '<program> <erase> <getpartitiontable>',
        note: 'Firehose commands. eMMC exposes 4 LUNs, UFS exposes 8.',
      },
    ],
  },
  {
    id: 'unisoc',
    vendor: 'UNISOC',
    protocol: 'BSL download mode',
    usbId: '1782:…',
    entry: 'Download mode — the boot ROM exposes the serial loader over USB.',
    source: 'src/spd.rs',
    cli: './target/release/flashpilot-bridge spd-detect',
    steps: [
      {
        title: 'Connect',
        wire: '0x00 then 0x80 / 0x81',
        note: 'BSL connect. The device acknowledges and reports its protocol version.',
      },
      {
        title: 'Read the chip type',
        wire: '0x07',
        note: 'Identifies the SoC before any write is attempted.',
      },
      {
        title: 'Read the chip UID',
        wire: '0x1a',
        note: 'Reads the unique device identifier.',
      },
      {
        title: 'Read flash',
        wire: '0x10, 0x11, 0x12',
        note: 'Start, middle and end of a flash read — the three-phase transfer.',
      },
      {
        title: 'Write flash',
        wire: '0x01, 0x02, 0x03, 0x04',
        note: 'Start, middle and end of the data, then execute it.',
      },
      {
        title: 'Repartition and power off',
        wire: '0x0b and 0x17',
        note: 'Partition table edits, then a clean shutdown so the phone restarts on its own.',
      },
    ],
  },
]
