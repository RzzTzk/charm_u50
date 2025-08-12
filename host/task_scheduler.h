#pragma once
#include <vector>
#include <map>
#include <CL/cl2.hpp>

class TaskScheduler {
public:
    struct KernelConfig {
        std::string name;
        cl::Kernel kernel;
        int hbm_channel_start;
        int hbm_channel_count;
    };

    void addKernel(const KernelConfig& config) {
        kernels_[config.name] = config;
    }

    void runTask(const std::string& name, int M, int K, int N) {
        auto& config = kernels_[name];
        cl::Buffer A, B, C;
        
        // 分配HBM缓冲区
        A = cl::Buffer(context_, CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX, 
                      M*K*sizeof(float), nullptr, &hbm_errors_[config.hbm_channel_start]);
        
        // 设置内核参数
        config.kernel.setArg(0, A);
        config.kernel.setArg(1, B);
        config.kernel.setArg(2, C);
        config.kernel.setArg(3, M);
        config.kernel.setArg(4, K);
        config.kernel.setArg(5, N);
        
        // 提交任务
        queue_.enqueueTask(config.kernel);
    }

private:
    std::map<std::string, KernelConfig> kernels_;
    cl::Context context_;
    cl::CommandQueue queue_;
    std::vector<cl_mem_ext_ptr_t> hbm_ptrs_;
};