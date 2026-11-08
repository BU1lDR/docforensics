# Raw file-structure check on the ext-test pack (whole tool)

Run: 2026-11-08 11:24 India Standard Time, commit bb08c8e, Windows 10, Python 3.11.9, 6 cores, CPU only.
120 cases (seeds 4300000 to 4300119), 181 s in all, 1.5 s a case.

A case without a planted change is a digital PDF, a PDF holding a scan, a JPEG or a PNG as the generator or the scanner wrote it. A planted case carries one change to the file's structure, and `expect` is the list of observations the check must show on it, fixed in datagen/structure_pack.py before the check was run on the pack. This is a measurement by construction: it shows what the check does with the changes it was written to look for, on files made by this project's generator. It says nothing about how often a real edit leaves such a change, and nothing about files made by other programs.

## In short

- Files without a planted change (60): an observation on 0, which is a false flag.
- Files with one planted change (60): every expected observation shown on 60; 80 of 80 expected observations shown. Missed: none.
- Observations that were not expected: 0.
- Limitations the check raised: 10: signed-then-added: Signature present, not verified (10).

## By kind

| kind | planted | files | expected observations shown | missed | stray |
|---|---|---|---|---|---|
| statement | no | 10 | 0 of 0 | 0 | 0 |
| payslip | no | 10 | 0 of 0 | 0 | 0 |
| padded | no | 10 | 0 of 0 | 0 | 0 |
| scan-pdf | no | 10 | 0 of 0 | 0 | 0 |
| scan-jpeg | no | 10 | 0 of 0 | 0 | 0 |
| scan-png | no | 10 | 0 of 0 | 0 | 0 |
| tail | yes | 10 | 10 of 10 | 0 | 0 |
| records | yes | 10 | 10 of 10 | 0 | 0 |
| signed-then-added | yes | 10 | 10 of 10 | 0 | 0 |
| attached | yes | 10 | 20 of 20 | 0 | 0 |
| rebuilt | yes | 10 | 10 of 10 | 0 | 0 |
| image-tail | yes | 10 | 20 of 20 | 0 | 0 |

## Every case

| case | kind | file | bytes | expected | shown | limitations | s |
|---|---|---|---|---|---|---|---|
| ext-test-s-0000 | statement | document.pdf | 14330 | - | - | - | 0.6 |
| ext-test-s-0001 | payslip | document.pdf | 9280 | - | - | - | 0.6 |
| ext-test-s-0002 | padded | document.pdf | 14423 | - | - | - | 0.5 |
| ext-test-s-0003 | scan-pdf | document.pdf | 683554 | - | - | - | 4.4 |
| ext-test-s-0004 | scan-jpeg | document.jpg | 679559 | - | - | - | 3.7 |
| ext-test-s-0005 | scan-png | document.png | 2315977 | - | - | - | 3.4 |
| ext-test-s-0006 | tail | document.pdf | 14296 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.6 |
| ext-test-s-0007 | records | document.pdf | 14669 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.6 |
| ext-test-s-0008 | signed-then-added | document.pdf | 14418 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.7 |
| ext-test-s-0009 | attached | document.pdf | 14702 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.5 |
| ext-test-s-0010 | rebuilt | document.pdf | 14382 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-test-s-0011 | image-tail | document.jpg | 678741 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.5 |
| ext-test-s-0012 | statement | document.pdf | 15620 | - | - | - | 0.5 |
| ext-test-s-0013 | payslip | document.pdf | 9496 | - | - | - | 0.6 |
| ext-test-s-0014 | padded | document.pdf | 16121 | - | - | - | 0.6 |
| ext-test-s-0015 | scan-pdf | document.pdf | 697677 | - | - | - | 3.5 |
| ext-test-s-0016 | scan-jpeg | document.jpg | 698238 | - | - | - | 4.0 |
| ext-test-s-0017 | scan-png | document.png | 2327790 | - | - | - | 3.5 |
| ext-test-s-0018 | tail | document.pdf | 15894 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.6 |
| ext-test-s-0019 | records | document.pdf | 16303 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.6 |
| ext-test-s-0020 | signed-then-added | document.pdf | 17260 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.7 |
| ext-test-s-0021 | attached | document.pdf | 16769 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-test-s-0022 | rebuilt | document.pdf | 15602 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-test-s-0023 | image-tail | document.jpg | 694823 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.6 |
| ext-test-s-0024 | statement | document.pdf | 14146 | - | - | - | 0.5 |
| ext-test-s-0025 | payslip | document.pdf | 9429 | - | - | - | 0.6 |
| ext-test-s-0026 | padded | document.pdf | 13191 | - | - | - | 0.5 |
| ext-test-s-0027 | scan-pdf | document.pdf | 681030 | - | - | - | 3.3 |
| ext-test-s-0028 | scan-jpeg | document.jpg | 681364 | - | - | - | 3.6 |
| ext-test-s-0029 | scan-png | document.png | 2312472 | - | - | - | 3.1 |
| ext-test-s-0030 | tail | document.pdf | 12743 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.6 |
| ext-test-s-0031 | records | document.pdf | 13200 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.6 |
| ext-test-s-0032 | signed-then-added | document.pdf | 15600 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-test-s-0033 | attached | document.pdf | 14773 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-test-s-0034 | rebuilt | document.pdf | 14467 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-test-s-0035 | image-tail | document.jpg | 679770 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.4 |
| ext-test-s-0036 | statement | document.pdf | 15179 | - | - | - | 0.5 |
| ext-test-s-0037 | payslip | document.pdf | 9273 | - | - | - | 0.5 |
| ext-test-s-0038 | padded | document.pdf | 15107 | - | - | - | 0.5 |
| ext-test-s-0039 | scan-pdf | document.pdf | 700299 | - | - | - | 3.3 |
| ext-test-s-0040 | scan-jpeg | document.jpg | 694565 | - | - | - | 3.6 |
| ext-test-s-0041 | scan-png | document.png | 2327418 | - | - | - | 3.1 |
| ext-test-s-0042 | tail | document.pdf | 15697 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.6 |
| ext-test-s-0043 | records | document.pdf | 15042 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-test-s-0044 | signed-then-added | document.pdf | 17404 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-test-s-0045 | attached | document.pdf | 15511 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-test-s-0046 | rebuilt | document.pdf | 15625 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.5 |
| ext-test-s-0047 | image-tail | document.jpg | 694376 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.6 |
| ext-test-s-0048 | statement | document.pdf | 13999 | - | - | - | 0.5 |
| ext-test-s-0049 | payslip | document.pdf | 9201 | - | - | - | 0.6 |
| ext-test-s-0050 | padded | document.pdf | 14418 | - | - | - | 0.5 |
| ext-test-s-0051 | scan-pdf | document.pdf | 684696 | - | - | - | 3.2 |
| ext-test-s-0052 | scan-jpeg | document.jpg | 681340 | - | - | - | 3.4 |
| ext-test-s-0053 | scan-png | document.png | 2317955 | - | - | - | 3.0 |
| ext-test-s-0054 | tail | document.pdf | 13255 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-test-s-0055 | records | document.pdf | 14548 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-test-s-0056 | signed-then-added | document.pdf | 15434 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-test-s-0057 | attached | document.pdf | 14049 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.5 |
| ext-test-s-0058 | rebuilt | document.pdf | 12742 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.5 |
| ext-test-s-0059 | image-tail | document.jpg | 680232 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.4 |
| ext-test-s-0060 | statement | document.pdf | 15646 | - | - | - | 0.5 |
| ext-test-s-0061 | payslip | document.pdf | 9272 | - | - | - | 0.5 |
| ext-test-s-0062 | padded | document.pdf | 15983 | - | - | - | 0.6 |
| ext-test-s-0063 | scan-pdf | document.pdf | 698171 | - | - | - | 3.3 |
| ext-test-s-0064 | scan-jpeg | document.jpg | 691286 | - | - | - | 3.6 |
| ext-test-s-0065 | scan-png | document.png | 2332207 | - | - | - | 3.3 |
| ext-test-s-0066 | tail | document.pdf | 15565 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-test-s-0067 | records | document.pdf | 15996 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-test-s-0068 | signed-then-added | document.pdf | 17610 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-test-s-0069 | attached | document.pdf | 15978 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.5 |
| ext-test-s-0070 | rebuilt | document.pdf | 14557 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-test-s-0071 | image-tail | document.jpg | 697737 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.6 |
| ext-test-s-0072 | statement | document.pdf | 14192 | - | - | - | 0.5 |
| ext-test-s-0073 | payslip | document.pdf | 9369 | - | - | - | 0.6 |
| ext-test-s-0074 | padded | document.pdf | 14186 | - | - | - | 0.5 |
| ext-test-s-0075 | scan-pdf | document.pdf | 681714 | - | - | - | 3.1 |
| ext-test-s-0076 | scan-jpeg | document.jpg | 680215 | - | - | - | 3.4 |
| ext-test-s-0077 | scan-png | document.png | 2315304 | - | - | - | 3.0 |
| ext-test-s-0078 | tail | document.pdf | 14364 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-test-s-0079 | records | document.pdf | 13597 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-test-s-0080 | signed-then-added | document.pdf | 15594 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-test-s-0081 | attached | document.pdf | 13092 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.5 |
| ext-test-s-0082 | rebuilt | document.pdf | 14179 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.5 |
| ext-test-s-0083 | image-tail | document.jpg | 681300 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.5 |
| ext-test-s-0084 | statement | document.pdf | 16197 | - | - | - | 0.5 |
| ext-test-s-0085 | payslip | document.pdf | 9363 | - | - | - | 0.5 |
| ext-test-s-0086 | padded | document.pdf | 14654 | - | - | - | 0.5 |
| ext-test-s-0087 | scan-pdf | document.pdf | 698666 | - | - | - | 3.4 |
| ext-test-s-0088 | scan-jpeg | document.jpg | 693204 | - | - | - | 3.6 |
| ext-test-s-0089 | scan-png | document.png | 2332086 | - | - | - | 3.2 |
| ext-test-s-0090 | tail | document.pdf | 16214 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-test-s-0091 | records | document.pdf | 16577 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-test-s-0092 | signed-then-added | document.pdf | 17545 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-test-s-0093 | attached | document.pdf | 16383 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.5 |
| ext-test-s-0094 | rebuilt | document.pdf | 16128 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.5 |
| ext-test-s-0095 | image-tail | document.jpg | 694208 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.6 |
| ext-test-s-0096 | statement | document.pdf | 14272 | - | - | - | 0.5 |
| ext-test-s-0097 | payslip | document.pdf | 9232 | - | - | - | 0.5 |
| ext-test-s-0098 | padded | document.pdf | 14030 | - | - | - | 0.5 |
| ext-test-s-0099 | scan-pdf | document.pdf | 684903 | - | - | - | 3.1 |
| ext-test-s-0100 | scan-jpeg | document.jpg | 677333 | - | - | - | 3.4 |
| ext-test-s-0101 | scan-png | document.png | 2315966 | - | - | - | 3.0 |
| ext-test-s-0102 | tail | document.pdf | 13744 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-test-s-0103 | records | document.pdf | 14537 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-test-s-0104 | signed-then-added | document.pdf | 15026 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-test-s-0105 | attached | document.pdf | 13106 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.5 |
| ext-test-s-0106 | rebuilt | document.pdf | 13709 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.5 |
| ext-test-s-0107 | image-tail | document.jpg | 678573 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.4 |
| ext-test-s-0108 | statement | document.pdf | 15107 | - | - | - | 0.5 |
| ext-test-s-0109 | payslip | document.pdf | 9217 | - | - | - | 0.6 |
| ext-test-s-0110 | padded | document.pdf | 16287 | - | - | - | 0.6 |
| ext-test-s-0111 | scan-pdf | document.pdf | 697891 | - | - | - | 3.3 |
| ext-test-s-0112 | scan-jpeg | document.jpg | 695594 | - | - | - | 3.8 |
| ext-test-s-0113 | scan-png | document.png | 2330033 | - | - | - | 3.3 |
| ext-test-s-0114 | tail | document.pdf | 15964 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-test-s-0115 | records | document.pdf | 16578 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-test-s-0116 | signed-then-added | document.pdf | 17361 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-test-s-0117 | attached | document.pdf | 16537 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-test-s-0118 | rebuilt | document.pdf | 16169 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-test-s-0119 | image-tail | document.jpg | 693193 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.7 |
