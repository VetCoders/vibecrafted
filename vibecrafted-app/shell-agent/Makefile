# shell-agent - UniFFI bridge + SwiftUI app
# Created by Vetcoders (c)2026 LibraxisAI

export MACOSX_DEPLOYMENT_TARGET ?= 14.0

.PHONY: help bindings xcode app app-debug dmg dmg-signed

HELP_C_CYAN   := \033[36m
HELP_C_GREEN  := \033[32m
HELP_C_YELLOW := \033[33m
HELP_C_RESET  := \033[0m

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
	@mkdir -p build
	@rm -rf build/Vibecrafted.app
	@set -o pipefail && xcodebuild -project app/Vibecrafted.xcodeproj -scheme Vibecrafted -configuration Debug -derivedDataPath build/DerivedData build 2>&1 | tail -20
	@BUILT_APP=$$(find build/DerivedData -name Vibecrafted.app -type d | head -1); \
		if [ -z "$$BUILT_APP" ]; then \
			echo "ERROR: Vibecrafted.app not found in build/DerivedData"; \
			exit 1; \
		fi; \
		cp -R "$$BUILT_APP" build/Vibecrafted.app
	@/usr/libexec/PlistBuddy -c "Set :CFBundleIconFile icon1" build/Vibecrafted.app/Contents/Info.plist 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string icon1" build/Vibecrafted.app/Contents/Info.plist
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
		cp ../target/release/rmcp-mux "$$BUILT_APP/Contents/MacOS/vc-mux-daemon"; \
		cp ../target/release/vc-mux-tray "$$BUILT_APP/Contents/MacOS/vc-mux-tray"; \
		cp ../target/release/voc "$$BUILT_APP/Contents/MacOS/voc"; \
		chmod +x "$$BUILT_APP/Contents/MacOS/"*; \
		./scripts/fix-dylib-install-names.sh "$$BUILT_APP"; \
		codesign --force --deep --sign - "$$BUILT_APP"; \
	fi

help:
	@printf "\n$(HELP_C_CYAN)shell-agent$(HELP_C_RESET) - UniFFI bridge + SwiftUI app\n\n"
	@printf "  $(HELP_C_YELLOW)BUILD$(HELP_C_RESET)\n"
	@printf "    $(HELP_C_GREEN)%-14s$(HELP_C_RESET) %s\n" "bindings" "Build Rust FFI and generate Swift bindings"
	@printf "    $(HELP_C_GREEN)%-14s$(HELP_C_RESET) %s\n" "xcode" "Generate app/Vibecrafted.xcodeproj"
	@printf "    $(HELP_C_GREEN)%-14s$(HELP_C_RESET) %s\n" "app" "Build and ad-hoc codesign Vibecrafted.app"
	@printf "    $(HELP_C_GREEN)%-14s$(HELP_C_RESET) %s\n" "app-debug" "Build app with release daemon binaries copied in"
	@printf "\n  $(HELP_C_YELLOW)PACKAGE$(HELP_C_RESET)\n"
	@printf "    $(HELP_C_GREEN)%-14s$(HELP_C_RESET) %s\n" "dmg" "Build unsigned/ad-hoc DMG"
	@printf "    $(HELP_C_GREEN)%-14s$(HELP_C_RESET) %s\n" "dmg-signed" "Build signed DMG"
