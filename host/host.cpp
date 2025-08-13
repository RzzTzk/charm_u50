#include "task_scheduler.h"
#include <iostream>
#include <CL/cl2.hpp>
#include <vector>
#include <fstream>
#include <nlohmann/json.hpp> //

// 辅助函数定义
cl::Device get_xilinx_device() { /* 同上 */ }
cl::Program load_xclbin(cl::Context context, const std::string& xclbin_path) { /* 同上 */ }
std::vector<Task> load_tasks(const std::string& task_file) { /* 同上 */ }

int main() {
    try {
        // 初始化OpenCL
        cl::Device device = get_xilinx_device();
        cl::Context context(device);
        cl::Program program = load_xclbin(context, "mm_accel.xclbin");
        
        // 初始化调度器
        TaskScheduler scheduler;
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
        
        // 加载并执行任务
        auto tasks = load_tasks("design_space/tasks.json");
        for (const auto& task : tasks) {
            scheduler.runTask(task.acc_type, task.M, task.K, task.N);
        }
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}