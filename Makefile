# Makefile for CHARM Alveo U50 Project (Full Version)
# Usage:
#   make all      - Build everything (default)
#   make xclbin   - Build only hardware accelerators
#   make host     - Build only host program
#   make clean    - Remove all generated files
#   make run      - Run the executable (after building)

# --- Project Configuration ---
PROJECT      := charm_u50
PLATFORM     := xilinx_u50_gen3x16_xdma_5_202210_1
XCLBIN       := build/mm_accel.xclbin
HOST_EXE     := build/host_exec

# --- Directory Structure ---
KERNEL_DIR   := kernels
HOST_DIR     := host
INCLUDE_DIR  := include
SCRIPT_DIR   := scripts
BUILD_DIR    := build
REPORT_DIR   := reports

# --- Toolchain ---
VPP          := v++
GXX          := g++
CLFLAGS      := -lOpenCL -lxrt_core
VPP_FLAGS    := -t hw --platform $(PLATFORM) --save-temps

# --- File Discovery ---
KERNEL_SRCS  := $(wildcard $(KERNEL_DIR)/mm_*.cpp)
KERNEL_OBJS  := $(patsubst $(KERNEL_DIR)/%.cpp,$(BUILD_DIR)/%.xo,$(KERNEL_SRCS))
HOST_SRCS    := $(wildcard $(HOST_DIR)/*.cpp)
HOST_OBJS    := $(patsubst $(HOST_DIR)/%.cpp,$(BUILD_DIR)/%.o,$(HOST_SRCS))

# --- Build Targets ---
all: $(XCLBIN) $(HOST_EXE)

xclbin: $(XCLBIN)

host: $(HOST_EXE)

run: $(HOST_EXE) $(XCLBIN)
	@echo "Running program..."
	@cd $(BUILD_DIR) && ./$(notdir $(HOST_EXE)) $(notdir $(XCLBIN))

codegen:
	python scripts/generate_hls.py --config design_space/acc_config.json
# --- XCLBIN Generation ---
$(XCLBIN): $(KERNEL_OBJS)
	@echo "Linking XCLBIN..."
	@mkdir -p $(BUILD_DIR) $(REPORT_DIR)
	$(VPP) $(VPP_FLAGS) -l \
		--config $(SCRIPT_DIR)/hbm_connectivity.cfg \
		--report_dir $(REPORT_DIR)/link \
		-o $@ $^
	@echo "XCLBIN generated at: $@"

$(BUILD_DIR)/%.xo: $(KERNEL_DIR)/%.cpp | codegen
	@echo "Compiling kernel $<..."
	@mkdir -p $(@D)
	$(VPP) $(VPP_FLAGS) -c \
		-k $(basename $(notdir $<)) \
		-I$(INCLUDE_DIR)/kernel \
		--report_dir $(REPORT_DIR)/compile_$(basename $(notdir $<)) \
		-o $@ $<

# --- Host Program ---
$(HOST_EXE): $(HOST_OBJS)
	@echo "Linking host program..."
	$(GXX) -std=c++11 \
		-I$(INCLUDE_DIR)/host \
		-I$(XILINX_XRT)/include \
		-L$(XILINX_XRT)/lib \
		$^ -o $@ $(CLFLAGS)
	@echo "Host executable: $@"

$(BUILD_DIR)/%.o: $(HOST_DIR)/%.cpp
	@mkdir -p $(@D)
	$(GXX) -std=c++11 \
		-I$(INCLUDE_DIR)/host \
		-I$(XILINX_XRT)/include \
		-c $< -o $@

# --- Utilities ---
clean:
	@echo "Cleaning build files..."
	@rm -rf $(BUILD_DIR) $(REPORT_DIR)
	@find . -name "*.log" -delete
	@find . -name "*.jou" -delete
5

# --- Environment Checks ---
check_env:
	@which $(VPP) >/dev/null || (echo "[ERROR] Vitis (v++) not found!"; exit 1)
	@test -d $(XILINX_XRT) || (echo "[ERROR] XILINX_XRT not set!"; exit 1)
	@echo "Environment check passed."

# --- Dependencies ---
$(KERNEL_OBJS): $(INCLUDE_DIR)/kernel/utils.h
$(HOST_OBJS): $(INCLUDE_DIR)/host/utils.h

.PHONY: all xclbin host run clean distclean check_env