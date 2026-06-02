# shell-agent - UniFFI bridge + SwiftUI app
# Created by VetCoders (c)2026 LibraxisAI

export MACOSX_DEPLOYMENT_TARGET ?= 14.0

.PHONY: bindings xcode app dmg dmg-signed

bindings:
	@echo "Building vibecrafted-shell-ffi (release)..."
	@cargo build -p vibecrafted-shell-ffi --release
	@./scripts/fix-dylib-install-names.sh
	@echo "Generating Swift bindings..."
	@cargo run -p vibecrafted-uniffi-bindgen -- generate --library ../target/release/libvibecrafted_shell_ffi.dylib --language swift --out-dir app/Vibecrafted/Bridge/
	@./scripts/normalize-bindings.sh app/Vibecrafted/Bridge
	@echo "Bindings ready: app/Vibecrafted/Bridge/"

xcode:
	@cd app && xcodegen generate
	@echo "Xcode project generated: app/Vibecrafted.xcodeproj"

app: bindings xcode
	@echo "Building Vibecrafted.app..."
	@rm -rf build/DerivedData build/Vibecrafted.app
	@set -o pipefail && xcodebuild -project app/Vibecrafted.xcodeproj -scheme Vibecrafted -configuration Debug -derivedDataPath build/DerivedData build 2>&1 | tail -20
	@BUILT_APP=$$(find build/DerivedData -name Vibecrafted.app -type d | head -1); \
		if [ -z "$$BUILT_APP" ]; then \
			echo "ERROR: Vibecrafted.app not found in build/DerivedData"; \
			exit 1; \
		fi; \
		cp -R "$$BUILT_APP" build/Vibecrafted.app
	@./scripts/fix-dylib-install-names.sh build/Vibecrafted.app
	@codesign --force --deep --sign - build/Vibecrafted.app
	@echo "App built: build/Vibecrafted.app"

dmg:
	@./scripts/build-dmg.sh

dmg-signed:
	@SIGNING_IDENTITY="Developer ID Application: Maciej Gad (MW223P3NPX)" ./scripts/build-dmg.sh

app-debug: bindings xcode
	@cargo build --workspace --release
	@xcodebuild -project app/Vibecrafted.xcodeproj -scheme Vibecrafted -configuration Debug -derivedDataPath build/DerivedData build
	@BUILT_APP=$$(find build/DerivedData -name Vibecrafted.app -type d | head -1); \
	if [ -n "$$BUILT_APP" ]; then \
		cp ../target/release/rust-mux "$$BUILT_APP/Contents/MacOS/vc-mux-daemon"; \
		cp ../target/release/vc-mux-tray "$$BUILT_APP/Contents/MacOS/vc-mux-tray"; \
		cp ../target/release/vc-operator "$$BUILT_APP/Contents/MacOS/vc-operator-tui"; \
		chmod +x "$$BUILT_APP/Contents/MacOS/"*; \
		./scripts/fix-dylib-install-names.sh "$$BUILT_APP"; \
		codesign --force --deep --sign - "$$BUILT_APP"; \
	fi
