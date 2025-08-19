set kernel_list {
    "mm_large"
    "mm_small"
}

foreach kernel $kernel_list {
    set kernel_xo [file rootname $kernel].xo
    puts "Compiling $kernel..."
    
    # 综合内核
    v++ -t hw --platform xilinx_u50_gen3x16_xdma_5_202210_1 \
        -c -k $kernel -o $kernel_xo kernels/${kernel}.cpp
    
    # 生成全局头文件
    if {![file exists "kernels/${kernel}.h"]} {
        set fd [open "kernels/${kernel}.h" w]
        puts $fd "#ifndef _${kernel}_H_"
        puts $fd "#define _${kernel}_H_"
        puts $fd "extern \"C\" {"
        puts $fd "void $kernel("
        puts $fd "    const float* A,"
        puts $fd "    const float* B,"
        puts $fd "    float* C,"
        puts $fd "    int M, int K, int N"
        puts $fd ");"
        puts $fd "}"
        puts $fd "#endif"
        close $fd
    }
}
# 链接生成xclbin
v++ -l -t hw --platform xilinx_u50_gen3x16_xdma_5_202210_1 \
    --config scripts/hbm_connectivity.cfg \
    -o mm_accel.xclbin mm_large.xo mm_small.xo
