#include "task_scheduler.h"
#include <fstream>
#include <iostream>

int main() {
    // 初始化OpenCL/XRT
    cl::Device device = get_xilinx_device();
    cl::Context context(device);
    cl::Program program = load_xclbin(context, "mm_accel.xclbin");
    
    TaskScheduler scheduler;
    
    // 注册加速器
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
    
    // 从JSON加载任务配置
    auto tasks = load_tasks("design_space/tasks.json");
    
    // 执行任务调度
    for (auto& task : tasks) {
        if (task.M > 1024) {
            scheduler.runTask("mm_large", task.M, task.K, task.N);
        } else {
            scheduler.runTask("mm_small", task.M, task.K, task.N);
        }
    }
    
    return 0;
}