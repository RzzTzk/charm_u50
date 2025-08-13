# Makefile for CHARM Alveo U50 Project
# Usage: 
#   make all      - Compile everything (default)
#   make xclbin   - Only generate mm_accel.xclbin
#   make host     - Only compile host program
#   make clean    - Remove all generated files

# --- 配置区域 ---
# 平台设置
PLATFORM      := xilinx_u50_gen3x16_xdma_5_202210_1
XCLBIN_NAME   := mm_accel.xclbin
HOST_EXEC     := host_executable

# 目录结构
KERNEL_DIR    := kernels
HOST_DIR      := host
SCRIPT_DIR    := scripts
BUILD_DIR     := build
DESIGN_DIR    := design_space

# Vitis/V++ 工具链
VPP           := v++
GCC           := g++
CLFLAGS       := -lopencl -lxrt_core

# --- 自动生成文件列表 ---
KERNEL_SRCS   := $(wildcard $(KERNEL_DIR)/mm_*.cpp)
KERNEL_OBJS   := $(patsubst $(KERNEL_DIR)/%.cpp,$(BUILD_DIR)/%.xo,$(KERNEL_SRCS))
HOST_SRCS     := $(wildcard $(HOST_DIR)/*.cpp)
HOST_OBJS     := $(patsubst $(HOST_DIR)/%.cpp,$(BUILD_DIR)/%.o,$(HOST_SRCS))

# --- 主目标 ---
all: $(BUILD_DIR)/$(XCLBIN_NAME) $(BUILD_DIR)/$(HOST_EXEC)

# --- XCLBIN 生成规则 ---
$(BUILD_DIR)/$(XCLBIN_NAME): $(KERNEL_OBJS)
	@echo "Linking XCLBIN..."
	@mkdir -p $(@D)
	$(VPP) -l -t hw --platform $(PLATFORM) \
		--config $(SCRIPT_DIR)/hbm_connectivity.cfg \
		-o $@ $^
	@echo "XCLBIN generated at: $@"

$(BUILD_DIR)/%.xo: $(KERNEL_DIR)/%.cpp
	@echo "Compiling kernel $<..."
	@mkdir -p $(@D)
	$(VPP) -c -t hw --platform $(PLATFORM) \
		-k $(basename $(notdir $<)) \
		-I$(KERNEL_DIR) \
		-o $@ $<

# --- 主机程序编译规则 ---
$(BUILD_DIR)/$(HOST_EXEC): $(HOST_OBJS)
	@echo "Building host program..."
	$(GCC) -std=c++11 \
		-I$(XILINX_XRT)/include \
		-I$(XILINX_XRT)/include/CL \
		-L$(XILINX_XRT)/lib \
		$^ -o $@ $(CLFLAGS)
	@echo "Host executable: $@"

$(BUILD_DIR)/%.o: $(HOST_DIR)/%.cpp
	@mkdir -p $(@D)
	$(GCC) -std=c++11 \
		-I$(XILINX_XRT)/include \
		-I$(XILINX_XRT)/include/CL \
		-I$(HOST_DIR) \
		-c $< -o $@

# --- 实用目标 ---
run: $(BUILD_DIR)/$(HOST_EXEC) $(BUILD_DIR)/$(XCLBIN_NAME)
	@echo "Running program..."
	@cd $(BUILD_DIR) && ./$(HOST_EXEC) $(XCLBIN_NAME)

clean:
	@echo "Cleaning build files..."
	@rm -rf $(BUILD_DIR)
	@rm -f *.log *.jou

# --- 依赖检查 ---
check_env:
	@which $(VPP) >/dev/null || (echo "Error: Vitis (v++) not found!"; exit 1)
	@which $(GCC) >/dev/null || (echo "Error: GCC not found!"; exit 1)
	@test -d $(XILINX_XRT) || (echo "Error: XILINX_XRT not set!"; exit 1)

.PHONY: all clean run check_env