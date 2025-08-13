#include "task_scheduler.h"
#include <iostream>

int main() {
    try {
        // 初始化OpenCL
        cl::Device device = get_xilinx_device();
        cl::Context context(device);
        cl::Program program = load_xclbin(context, "mm_accel.xclbin");
        
        // 初始化调度器（传入context）
        TaskScheduler scheduler(context);
        
        // 注册加速器内核
        scheduler.addKernel({
            "mm_large", 
            cl::Kernel(program, "mm_large"),
            0,  // HBM起始通道
            16  // 占用通道数
        });
        
        scheduler.addKernel({
            "mm_small",
            cl::Kernel(program, "mm_small"),
            24, // HBM起始通道
            8   // 占用通道数
        });
        
        // 执行任务
        scheduler.runTask("mm_large", 3072, 1024, 1024);
        scheduler.runTask("mm_small", 512, 512, 64);
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}

// # 编译（添加XRT扩展头文件路径）
// g++ -std=c++11 -I$XILINX_XRT/include -I$XILINX_XRT/include/CL host/*.cpp -o host -L$XILINX_XRT/lib -lOpenCL -lxrt_core