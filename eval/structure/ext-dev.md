# Raw file-structure check on the ext-dev pack (whole tool)

Run: 2026-11-07 00:44 India Standard Time, commit efa5797, Windows 10, Python 3.11.9, 6 cores, CPU only.
120 cases (seeds 3300000 to 3300119), 172 s in all, 1.4 s a case.

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
| ext-dev-s-0000 | statement | document.pdf | 14175 | - | - | - | 0.6 |
| ext-dev-s-0001 | payslip | document.pdf | 9420 | - | - | - | 0.6 |
| ext-dev-s-0002 | padded | document.pdf | 13216 | - | - | - | 0.5 |
| ext-dev-s-0003 | scan-pdf | document.pdf | 685122 | - | - | - | 3.9 |
| ext-dev-s-0004 | scan-jpeg | document.jpg | 680952 | - | - | - | 3.3 |
| ext-dev-s-0005 | scan-png | document.png | 2317535 | - | - | - | 2.7 |
| ext-dev-s-0006 | tail | document.pdf | 13144 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-dev-s-0007 | records | document.pdf | 14354 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-dev-s-0008 | signed-then-added | document.pdf | 13952 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-dev-s-0009 | attached | document.pdf | 14747 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.5 |
| ext-dev-s-0010 | rebuilt | document.pdf | 13190 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.5 |
| ext-dev-s-0011 | image-tail | document.jpg | 682135 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.3 |
| ext-dev-s-0012 | statement | document.pdf | 16084 | - | - | - | 0.6 |
| ext-dev-s-0013 | payslip | document.pdf | 9291 | - | - | - | 0.6 |
| ext-dev-s-0014 | padded | document.pdf | 15719 | - | - | - | 0.6 |
| ext-dev-s-0015 | scan-pdf | document.pdf | 698024 | - | - | - | 3.2 |
| ext-dev-s-0016 | scan-jpeg | document.jpg | 688527 | - | - | - | 3.3 |
| ext-dev-s-0017 | scan-png | document.png | 2326804 | - | - | - | 3.0 |
| ext-dev-s-0018 | tail | document.pdf | 15146 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.6 |
| ext-dev-s-0019 | records | document.pdf | 16374 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.6 |
| ext-dev-s-0020 | signed-then-added | document.pdf | 17601 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-dev-s-0021 | attached | document.pdf | 16658 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-dev-s-0022 | rebuilt | document.pdf | 15715 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-dev-s-0023 | image-tail | document.jpg | 691627 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.3 |
| ext-dev-s-0024 | statement | document.pdf | 13217 | - | - | - | 0.5 |
| ext-dev-s-0025 | payslip | document.pdf | 9304 | - | - | - | 0.6 |
| ext-dev-s-0026 | padded | document.pdf | 14346 | - | - | - | 0.5 |
| ext-dev-s-0027 | scan-pdf | document.pdf | 685026 | - | - | - | 2.9 |
| ext-dev-s-0028 | scan-jpeg | document.jpg | 680764 | - | - | - | 3.1 |
| ext-dev-s-0029 | scan-png | document.png | 2314613 | - | - | - | 2.7 |
| ext-dev-s-0030 | tail | document.pdf | 14314 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.6 |
| ext-dev-s-0031 | records | document.pdf | 14794 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.6 |
| ext-dev-s-0032 | signed-then-added | document.pdf | 14466 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-dev-s-0033 | attached | document.pdf | 14764 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-dev-s-0034 | rebuilt | document.pdf | 13224 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-dev-s-0035 | image-tail | document.jpg | 681414 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.3 |
| ext-dev-s-0036 | statement | document.pdf | 15614 | - | - | - | 0.5 |
| ext-dev-s-0037 | payslip | document.pdf | 9299 | - | - | - | 0.6 |
| ext-dev-s-0038 | padded | document.pdf | 14685 | - | - | - | 0.5 |
| ext-dev-s-0039 | scan-pdf | document.pdf | 698466 | - | - | - | 3.1 |
| ext-dev-s-0040 | scan-jpeg | document.jpg | 696636 | - | - | - | 3.4 |
| ext-dev-s-0041 | scan-png | document.png | 2328680 | - | - | - | 2.8 |
| ext-dev-s-0042 | tail | document.pdf | 16165 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-dev-s-0043 | records | document.pdf | 16578 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.6 |
| ext-dev-s-0044 | signed-then-added | document.pdf | 17635 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-dev-s-0045 | attached | document.pdf | 16589 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-dev-s-0046 | rebuilt | document.pdf | 15934 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-dev-s-0047 | image-tail | document.jpg | 692187 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.6 |
| ext-dev-s-0048 | statement | document.pdf | 13741 | - | - | - | 0.5 |
| ext-dev-s-0049 | payslip | document.pdf | 9232 | - | - | - | 0.6 |
| ext-dev-s-0050 | padded | document.pdf | 14063 | - | - | - | 0.5 |
| ext-dev-s-0051 | scan-pdf | document.pdf | 686719 | - | - | - | 3.2 |
| ext-dev-s-0052 | scan-jpeg | document.jpg | 680710 | - | - | - | 3.3 |
| ext-dev-s-0053 | scan-png | document.png | 2318772 | - | - | - | 2.7 |
| ext-dev-s-0054 | tail | document.pdf | 14091 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-dev-s-0055 | records | document.pdf | 14756 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-dev-s-0056 | signed-then-added | document.pdf | 13961 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-dev-s-0057 | attached | document.pdf | 14610 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-dev-s-0058 | rebuilt | document.pdf | 14396 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.5 |
| ext-dev-s-0059 | image-tail | document.jpg | 679609 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.2 |
| ext-dev-s-0060 | statement | document.pdf | 15672 | - | - | - | 0.6 |
| ext-dev-s-0061 | payslip | document.pdf | 9336 | - | - | - | 0.6 |
| ext-dev-s-0062 | padded | document.pdf | 16082 | - | - | - | 0.5 |
| ext-dev-s-0063 | scan-pdf | document.pdf | 697815 | - | - | - | 3.3 |
| ext-dev-s-0064 | scan-jpeg | document.jpg | 695703 | - | - | - | 3.4 |
| ext-dev-s-0065 | scan-png | document.png | 2328135 | - | - | - | 3.0 |
| ext-dev-s-0066 | tail | document.pdf | 15920 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.6 |
| ext-dev-s-0067 | records | document.pdf | 16554 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.6 |
| ext-dev-s-0068 | signed-then-added | document.pdf | 16488 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-dev-s-0069 | attached | document.pdf | 16046 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-dev-s-0070 | rebuilt | document.pdf | 15677 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-dev-s-0071 | image-tail | document.jpg | 691966 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.2 |
| ext-dev-s-0072 | statement | document.pdf | 13211 | - | - | - | 0.6 |
| ext-dev-s-0073 | payslip | document.pdf | 9275 | - | - | - | 0.6 |
| ext-dev-s-0074 | padded | document.pdf | 13665 | - | - | - | 0.5 |
| ext-dev-s-0075 | scan-pdf | document.pdf | 685564 | - | - | - | 3.1 |
| ext-dev-s-0076 | scan-jpeg | document.jpg | 681944 | - | - | - | 3.4 |
| ext-dev-s-0077 | scan-png | document.png | 2316791 | - | - | - | 2.8 |
| ext-dev-s-0078 | tail | document.pdf | 13731 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.6 |
| ext-dev-s-0079 | records | document.pdf | 13162 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.6 |
| ext-dev-s-0080 | signed-then-added | document.pdf | 14934 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.7 |
| ext-dev-s-0081 | attached | document.pdf | 14061 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.7 |
| ext-dev-s-0082 | rebuilt | document.pdf | 14240 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-dev-s-0083 | image-tail | document.jpg | 679330 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.2 |
| ext-dev-s-0084 | statement | document.pdf | 15120 | - | - | - | 0.5 |
| ext-dev-s-0085 | payslip | document.pdf | 9522 | - | - | - | 0.6 |
| ext-dev-s-0086 | padded | document.pdf | 15120 | - | - | - | 0.5 |
| ext-dev-s-0087 | scan-pdf | document.pdf | 701887 | - | - | - | 3.4 |
| ext-dev-s-0088 | scan-jpeg | document.jpg | 695315 | - | - | - | 3.4 |
| ext-dev-s-0089 | scan-png | document.png | 2331248 | - | - | - | 3.0 |
| ext-dev-s-0090 | tail | document.pdf | 15658 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-dev-s-0091 | records | document.pdf | 16534 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-dev-s-0092 | signed-then-added | document.pdf | 15873 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-dev-s-0093 | attached | document.pdf | 16310 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-dev-s-0094 | rebuilt | document.pdf | 16154 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-dev-s-0095 | image-tail | document.jpg | 695898 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.3 |
| ext-dev-s-0096 | statement | document.pdf | 12728 | - | - | - | 0.5 |
| ext-dev-s-0097 | payslip | document.pdf | 9200 | - | - | - | 0.6 |
| ext-dev-s-0098 | padded | document.pdf | 14312 | - | - | - | 0.6 |
| ext-dev-s-0099 | scan-pdf | document.pdf | 684057 | - | - | - | 3.1 |
| ext-dev-s-0100 | scan-jpeg | document.jpg | 681869 | - | - | - | 3.1 |
| ext-dev-s-0101 | scan-png | document.png | 2319168 | - | - | - | 2.7 |
| ext-dev-s-0102 | tail | document.pdf | 14482 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.5 |
| ext-dev-s-0103 | records | document.pdf | 14400 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.5 |
| ext-dev-s-0104 | signed-then-added | document.pdf | 13941 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.6 |
| ext-dev-s-0105 | attached | document.pdf | 14756 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.5 |
| ext-dev-s-0106 | rebuilt | document.pdf | 12693 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-dev-s-0107 | image-tail | document.jpg | 681171 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.2 |
| ext-dev-s-0108 | statement | document.pdf | 15979 | - | - | - | 0.5 |
| ext-dev-s-0109 | payslip | document.pdf | 9499 | - | - | - | 0.6 |
| ext-dev-s-0110 | padded | document.pdf | 15122 | - | - | - | 0.6 |
| ext-dev-s-0111 | scan-pdf | document.pdf | 697674 | - | - | - | 2.9 |
| ext-dev-s-0112 | scan-jpeg | document.jpg | 691597 | - | - | - | 3.4 |
| ext-dev-s-0113 | scan-png | document.png | 2328034 | - | - | - | 2.8 |
| ext-dev-s-0114 | tail | document.pdf | 15924 | Bytes follow the last end-of-file marker | Bytes follow the last end-of-file marker | - | 0.6 |
| ext-dev-s-0115 | records | document.pdf | 16728 | The /Info record and the XMP packet disagree | The /Info record and the XMP packet disagree | - | 0.6 |
| ext-dev-s-0116 | signed-then-added | document.pdf | 15916 | Content follows the signed byte range | Content follows the signed byte range | Signature present, not verified | 0.7 |
| ext-dev-s-0117 | attached | document.pdf | 14987 | PDF carries action keys; PDF carries an embedded file | PDF carries action keys; PDF carries an embedded file | - | 0.6 |
| ext-dev-s-0118 | rebuilt | document.pdf | 16261 | The file's index had to be rebuilt to be read | The file's index had to be rebuilt to be read | - | 0.6 |
| ext-dev-s-0119 | image-tail | document.jpg | 693298 | Bytes follow the end of the image; Image metadata names image-editing software | Bytes follow the end of the image; Image metadata names image-editing software | - | 3.3 |
