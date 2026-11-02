#!/bin/sh
# Render the editable local-network SVG to the README's PNG on macOS.
set -eu

if [ "$(uname -s)" != Darwin ] || ! command -v qlmanage >/dev/null 2>&1 || ! command -v swift >/dev/null 2>&1; then
    echo 'This diagram refresh requires macOS, Quick Look and Swift.' >&2
    exit 1
fi
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
task_dir=$(mktemp -d "${TMPDIR:-/tmp}/media-diagram.XXXXXXXX")
trap 'rm -rf "$task_dir"' EXIT HUP INT TERM
qlmanage -t -s 1600 -o "$task_dir" "$repo_root/docs/diagrams/local-network.svg" >/dev/null
swift - "$task_dir/local-network.svg.png" "$task_dir/local-network.png" <<'SWIFT'
import AppKit
import ImageIO
import UniformTypeIdentifiers

let input = URL(fileURLWithPath: CommandLine.arguments[1]) as CFURL
let output = URL(fileURLWithPath: CommandLine.arguments[2]) as CFURL
guard let source = CGImageSourceCreateWithURL(input, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil),
      let cropped = image.cropping(to: CGRect(x: 0, y: 0, width: 1600, height: 840)),
      let destination = CGImageDestinationCreateWithURL(output, UTType.png.identifier as CFString, 1, nil)
else { fatalError("Could not render the local-network diagram") }
CGImageDestinationAddImage(destination, cropped, nil)
if !CGImageDestinationFinalize(destination) { fatalError("Could not save the local-network diagram") }
SWIFT
cp "$task_dir/local-network.png" "$repo_root/docs/diagrams/local-network.png"
