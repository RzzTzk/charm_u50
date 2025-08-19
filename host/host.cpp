#include "../include/host/utils.h"
#include "task_scheduler.h"
#include <iostream>
#include <CL/cl2.hpp>
#include <CL/cl_ext_xilinx.h>
int main() {
    try {

        cl::Device device = get_xilinx_device();
        cl::Context context(device);
        cl::Program program = load_xclbin(context, "mm_accel.xclbin");
        ）
        TaskScheduler scheduler(context);
        
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
