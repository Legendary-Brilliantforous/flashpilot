# usb/ — USB transport
All USB/Touch layers moved here: rusb glue, descriptors, kernel detach.

```
usb/
  usb.rs       (712 lines)  — core detect, descriptors, kernel detach
  bulk.rs      (258 lines)  — bulk endpoints, bulk_send, bulk_session
  hid.rs       (200 lines)  — HID interfaces for Samsung
  mtp.rs       (295 lines)  — MTP layer
  at.rs        (322 lines)  — AT over CDC ACM
  bulk.rs, hid.rs already belong here logically; will be moved from src/
  config.rs    (272 lines)  — usb/ config + timeouts
```

No phone flashing logic here, only transport.
