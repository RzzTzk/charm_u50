#pragma once
#include <CL/opencl.hpp>  // 更新头文件
#include <vector>
#include <map>

class TaskScheduler {
public:
    struct KernelConfig {
        std::string name;
        cl::Kernel kernel;
        int hbm_channel_start;
        int hbm_channel_count;
    };

    TaskScheduler(cl::Context& context) : context_(context) {
        hbm_ptrs_.resize(32);
        for (int i = 0; i < 32; i++) {
            hbm_ptrs_[i].flags = i | XCL_MEM_TOPOLOGY;
            hbm_ptrs_[i].param = 0;
            hbm_ptrs_[i].obj = nullptr;
        }
    }

    void runTask(const std::string& name, int M, int K, int N) {
        auto& config = kernels_[name];
        cl::CommandQueue queue(context_, CL_QUEUE_PROFILING_ENABLE);
        
        // 使用NDRange接口替代弃用的enqueueTask
        queue.enqueueNDRangeKernel(
            config.kernel,
            cl::NullRange,
            cl::NDRange(1),
            cl::NullRange
        );
        queue.finish();
    }

private:
    cl::Context& context_;
    std::map<std::string, KernelConfig> kernels_;
    std::vector<cl_mem_ext_ptr_t> hbm_ptrs_;
};