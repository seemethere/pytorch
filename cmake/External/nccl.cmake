if(NOT __NCCL_INCLUDED)
  set(__NCCL_INCLUDED TRUE)

  if(USE_SYSTEM_NCCL)
    # NCCL_ROOT, NCCL_LIB_DIR, NCCL_INCLUDE_DIR will be accounted in the following line.
    find_package(NCCL REQUIRED)
    if(NCCL_FOUND)
      add_library(__caffe2_nccl INTERFACE)
      target_link_libraries(__caffe2_nccl INTERFACE ${NCCL_LIBRARIES})
      target_include_directories(__caffe2_nccl INTERFACE ${NCCL_INCLUDE_DIRS})
    endif()
  else()
    torch_cuda_get_nvcc_gencode_flag(NVCC_GENCODE)
    string(REPLACE "-gencode;" "-gencode=" NVCC_GENCODE "${NVCC_GENCODE}")
    # this second replacement is needed when there are multiple archs
    string(REPLACE ";-gencode" " -gencode" NVCC_GENCODE "${NVCC_GENCODE}")

    set(__NCCL_BUILD_DIR "${CMAKE_CURRENT_BINARY_DIR}/nccl")
    ExternalProject_Add(nccl_external
      SOURCE_DIR ${PROJECT_SOURCE_DIR}/third_party/nccl/nccl
      BUILD_IN_SOURCE 1
      CONFIGURE_COMMAND ""
      BUILD_COMMAND
        env
        # TODO: remove these flags when
        # https://github.com/pytorch/pytorch/issues/13362 is fixed
        "CCACHE_DISABLE=1"
        "SCCACHE_DISABLE=1"
        make
        "CXX=${CMAKE_CXX_COMPILER}"
        "CUDA_HOME=${CUDA_TOOLKIT_ROOT_DIR}"
        "NVCC=${CUDA_NVCC_EXECUTABLE}"
        "NVCC_GENCODE=${NVCC_GENCODE}"
        "BUILDDIR=${__NCCL_BUILD_DIR}"
        "VERBOSE=0"
        "-j"
        BUILD_BYPRODUCTS "${__NCCL_BUILD_DIR}/lib/libnccl_static.a"
      INSTALL_COMMAND ""
      )

    add_custom_command(
      OUTPUT "${__NCCL_BUILD_DIR}/lib/libnccl_slim_static.a"
      DEPENDS nccl_external
      COMMAND "${CMAKE_COMMAND}" -E make_directory "${__NCCL_BUILD_DIR}/objects"
      COMMAND pushd objects
      COMMAND "${CMAKE_AR}" x "${__NCCL_BUILD_DIR}/lib/libnccl_static.a"
      COMMAND for obj in all_gather_* all_reduce_* broadcast_* reduce_*.o$<SEMICOLON> do "${CMAKE_OBJCOPY}" --remove-relocations .nvFatBinSegment --remove-section __nv_relfatbin $$obj$<SEMICOLON> done
      COMMAND "${CMAKE_AR}" cr "${__NCCL_BUILD_DIR}/lib/libnccl_slim_static.a" "*.o"
      COMMAND popd
      COMMAND "${CMAKE_COMMAND}" -E remove_directory "${__NCCL_BUILD_DIR}/objects"
      WORKING_DIRECTORY "${__NCCL_BUILD_DIR}"
      COMMENT "Slimming NCCL"
    )
    add_custom_target(nccl_slim_external DEPENDS "${__NCCL_BUILD_DIR}/lib/libnccl_slim_static.a")

    set(NCCL_FOUND TRUE)
    add_library(__caffe2_nccl INTERFACE)
    # The following old-style variables are set so that other libs, such as Gloo,
    # can still use it.
    set(NCCL_INCLUDE_DIRS ${__NCCL_BUILD_DIR}/include)
    set(NCCL_LIBRARIES ${__NCCL_BUILD_DIR}/lib/libnccl_slim_static.a)
    add_dependencies(__caffe2_nccl nccl_slim_external)
    target_link_libraries(__caffe2_nccl INTERFACE ${NCCL_LIBRARIES})
    target_include_directories(__caffe2_nccl INTERFACE ${NCCL_INCLUDE_DIRS})
  endif()
endif()
