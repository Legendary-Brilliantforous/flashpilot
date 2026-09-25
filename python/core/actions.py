"""Job/mode -> backend action-id mapping (pre-execution capability gate).

The GUI's job names (``core.JOBS`` keys) are human workflows; the Rust
``ActionRegistry`` speaks action ids (``frp_workflow``, ``samsung_odin_flash``,
...). This table translates so the runners can ask the backend
(``bridge.validate_action``) whether a job may run on the selected device
*before* locking, spawning, or executing anything.

``None`` = job not modeled in the registry yet (experimental/domain flows
such as Knox, QCN, IMEI, carrier unlock): the gate SKIPS those rather than
blocking work the registry cannot judge. A list means every entry is tried
and at least one must validate (e.g. MTK mode accepts a BROM flash or a
crash-to-BROM, whichever the current state allows).
"""

JOB_ACTION_IDS = {
    "Read Device Info": ["read_device_info"],
    "Reboot": ["reboot_device"],
    "Remove FRP": ["frp_workflow"],
    "Remove MDM": ["mdm_workflow"],
    "Remove Screen Lock": ["screen_lock_workflow"],
    ("Flash Firmware", "Download mode"): ["samsung_odin_flash"],
    ("Flash Firmware", "MTK BROM"): ["mtk_brom_flash"],
    ("Flash Firmware", "MTK"): ["mtk_brom_flash", "mtk_crash_to_brom"],
    ("Flash Firmware", "EDL"): ["qualcomm_edl_flash"],
    ("Flash Firmware", "SPD"): ["spd_flash"],
}


def actions_for_job(job, mode):
    """Candidate backend action ids for (job, mode), or None when the job
    is not modeled (gate skips). Specific (job, mode) wins over bare job."""
    actions = JOB_ACTION_IDS.get((job, mode))
    if actions is None:
        actions = JOB_ACTION_IDS.get(job)
    return actions


def check_job_allowed(job, mode, device_key, validate):
    """Try each candidate action via ``validate(device_key, action_id)``.

    Returns (True, None) when at least one validates — or when the job is
    unmapped / key-less (legacy passthrough). Returns (False, error) when
    every candidate is rejected. ``validate`` is ``bridge.validate_action``
    in production, a stub in tests. A missing bridge binary (code
    BINARY_NOT_FOUND) passes through: the flow itself reports it, and a
    gate "unsupported" would mislead.
    """
    return check_actions(device_key, actions_for_job(job, mode), validate)


def check_actions(device_key, action_ids, validate):
    """Same as :func:`check_job_allowed` for an explicit candidate list.

    ``action_ids`` None/empty = unmapped command the registry cannot judge:
    skip (True, None). Otherwise every entry is tried and at least one must
    validate.
    """
    if not action_ids or not device_key:
        return True, None
    last = None
    for aid in action_ids:
        try:
            validate(device_key, aid)
            return True, None
        except Exception as e:  # noqa: BLE001 - decided below
            if getattr(e, "code", "") == "BINARY_NOT_FOUND":
                return True, None
            last = e
    return False, last


# Chip-page direct commands (bridge argv[0]) -> candidate backend actions.
# None/absent = mechanism the registry does not model yet (exploit/bypass
# primitives, ADB-enable helpers): the gate skips those rather than blocking
# work it cannot judge. "adb_shell" covers the ADB-mechanism tools (triage,
# battery, network) for display gating.
CHIP_COMMAND_ACTIONS = {
    # MTK page (target at argv[1])
    "mtk-flash": ["mtk_brom_flash"],
    "mtk-flash-part": ["mtk_brom_flash"],
    "mtk-frp": ["frp_workflow"],
    "mtk-frp-gpt": ["frp_workflow"],
    "mtk-frp-brom": ["frp_workflow"],
    "mtk-backup": ["backup_partitions"],
    "mtk-gpt": ["read_device_info"],
    "mtk-check-scatter": ["read_device_info"],
    "mtk-reboot": ["reboot_device"],
    # Qualcomm page (target at argv[1])
    "qcom-flash": ["qualcomm_edl_flash"],
    "qcom-flash-one": ["qualcomm_edl_flash"],
    "qcom-backup": ["backup_partitions"],
    "qcom-frp-reset": ["frp_workflow"],
    "qcom-info": ["read_device_info"],
    "qcom-partitions": ["read_device_info"],
    "qcom-reboot": ["reboot_device"],
    # SPD page (target at argv[1])
    "spd-flash": ["spd_flash"],
    "spd-format": ["spd_flash"],
    "spd-frp": ["frp_workflow"],
    "spd-readback": ["backup_partitions"],
    "spd-backup": ["backup_partitions"],
    "spd-info": ["read_device_info"],
    "spd-partitions": ["read_device_info"],
    "spd-boot": ["reboot_device"],
    "spd-reset": ["reboot_device"],
    # ADB-mechanism tools (triage, battery, network pages)
    "adb_shell": ["adb_shell"],
}


def actions_for_command(cmd):
    """Candidate backend action ids for a chip-page bridge command
    (argv[0]), or None when the command is not modeled (gate skips)."""
    if not cmd:
        return None
    return CHIP_COMMAND_ACTIONS.get(cmd)


def button_allowed(job=None, mode=None, command=None, allowed_ids=()):
    """Display-gating decision for one button: True = enabled.

    ``command`` (bridge argv[0] / tool mechanism id) wins when given,
    else the (job, mode) mapping. Unmapped buttons fail OPEN (True): the
    display layer must never brick the UI — enforcement lives in the
    pre-execution gate, not here.
    """
    allowed = set(allowed_ids or ())
    if command:
        cands = actions_for_command(command)
        if cands is None:
            return True
        return any(c in allowed for c in cands)
    cands = actions_for_job(job, mode)
    if cands is None:
        return True
    return any(c in allowed for c in cands)
