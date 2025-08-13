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

    TaskScheduler(cl::Context& context) : context_(context) {
        // 初始化HBM错误处理缓冲区（32个通道）
        hbm_ptrs_.resize(32);
        for (int i = 0; i < 32; i++) {
            hbm_ptrs_[i].flags = i | XCL_MEM_TOPOLOGY; // 绑定到具体HBM通道
            hbm_ptrs_[i].param = 0;
            hbm_ptrs_[i].obj = nullptr;
        }
    }

    void addKernel(const KernelConfig& config) {
        kernels_[config.name] = config;
    }

    void runTask(const std::string& name, int M, int K, int N) {
        auto& config = kernels_[name];
        
        // 创建HBM缓冲区
        cl_mem_ext_ptr_t a_ext = hbm_ptrs_[config.hbm_channel_start];
        cl_mem_ext_ptr_t b_ext = hbm_ptrs_[config.hbm_channel_start + config.hbm_channel_count/2];
        cl_mem_ext_ptr_t c_ext = hbm_ptrs_[config.hbm_channel_start];
        
        cl::Buffer A(context_, CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX, 
                    M*K*sizeof(float), &a_ext);
        cl::Buffer B(context_, CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX,
                    K*N*sizeof(float), &b_ext);
        cl::Buffer C(context_, CL_MEM_WRITE_ONLY | CL_MEM_EXT_PTR_XILINX,
                    M*N*sizeof(float), &c_ext);

        // 设置内核参数
        config.kernel.setArg(0, A);
        config.kernel.setArg(1, B);
        config.kernel.setArg(2, C);
        config.kernel.setArg(3, M);
        config.kernel.setArg(4, K);
        config.kernel.setArg(5, N);
        
        // 提交任务
        cl::CommandQueue queue(context_, context_.getInfo<CL_CONTEXT_DEVICES>()[0]);
        queue.enqueueTask(config.kernel);
        queue.finish();
    }

private:
    cl::Context& context_;
    std::map<std::string, KernelConfig> kernels_;
    std::vector<cl_mem_ext_ptr_t> hbm_ptrs_; // 新增：HBM通道配置
};