'use strict';

// Suppress ZXing's internal console.warn noise
const _warn = console.warn;
console.warn = () => {};

const { Jimp } = require('jimp');
const {
  MultiFormatReader,
  BinaryBitmap,
  HybridBinarizer,
  RGBLuminanceSource,
  DecodeHintType,
  BarcodeFormat,
} = require('@zxing/library');

const FORMATS = [
  BarcodeFormat.EAN_13, BarcodeFormat.EAN_8,
  BarcodeFormat.UPC_A, BarcodeFormat.UPC_E,
  BarcodeFormat.CODE_128, BarcodeFormat.CODE_39,
  BarcodeFormat.CODE_93, BarcodeFormat.ITF,
  BarcodeFormat.QR_CODE, BarcodeFormat.DATA_MATRIX,
  BarcodeFormat.PDF_417,
];

function buildReader() {
  const hints = new Map();
  hints.set(DecodeHintType.POSSIBLE_FORMATS, FORMATS);
  hints.set(DecodeHintType.TRY_HARDER, true);
  const reader = new MultiFormatReader();
  reader.setHints(hints);
  return reader;
}

function toLuminance(bitmapData, width, height) {
  const lum = new Uint8ClampedArray(width * height);
  for (let i = 0; i < width * height; i++) {
    lum[i] = (bitmapData[i * 4] * 299 + bitmapData[i * 4 + 1] * 587 + bitmapData[i * 4 + 2] * 114) / 1000;
  }
  return lum;
}

function rotate90cw(lum, w, h) {
  const out = new Uint8ClampedArray(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      out[x * h + (h - 1 - y)] = lum[y * w + x];
    }
  }
  return { lum: out, width: h, height: w };
}

function tryDecode(reader, lum, w, h) {
  try {
    const src = new RGBLuminanceSource(lum, w, h);
    const bmp = new BinaryBitmap(new HybridBinarizer(src));
    return reader.decode(bmp).getText();
  } catch (_) {
    return null;
  }
}

function tryAllRotations(reader, lum, w, h) {
  let cl = lum, cw = w, ch = h;
  for (let rot = 0; rot < 4; rot++) {
    const r = tryDecode(reader, cl, cw, ch);
    if (r) return r;
    const rotated = rotate90cw(cl, cw, ch);
    cl = rotated.lum; cw = rotated.width; ch = rotated.height;
  }
  return null;
}

async function decode(imagePath) {
  const image = await Jimp.read(imagePath);
  const reader = buildReader();
  const { width, height } = image.bitmap;
  const lum = toLuminance(image.bitmap.data, width, height);
  return tryAllRotations(reader, lum, width, height);
}

const imagePath = process.argv[2];
if (!imagePath) {
  process.stderr.write('Usage: node decode.js <image_path>\n');
  process.exit(2);
}

decode(imagePath)
  .then((code) => {
    if (code) {
      process.stdout.write(code + '\n');
      process.exit(0);
    } else {
      process.exit(1);
    }
  })
  .catch((err) => {
    process.stderr.write(err.message + '\n');
    process.exit(1);
  });
