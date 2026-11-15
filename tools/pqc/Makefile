ROOT := $(abspath ../..)
BUILD_DIR ?= $(ROOT)/evidence/local/pqc-build
FN := $(ROOT)/firmware/lib/c-fn-dsa
ML := $(ROOT)/firmware/lib/mlkem-native
PROOF := $(ROOT)/firmware/lib/pqc-proof/src
CPPFLAGS := -I$(FN) -I$(ML) -I$(PROOF) -DMLK_CONFIG_PARAMETER_SET=512 -DMLK_CONFIG_NAMESPACE_PREFIX=pqc_mlkem -DMLK_CONFIG_NO_RANDOMIZED_API -DMLK_CONFIG_SERIAL_FIPS202_ONLY -DFNDSA_AVX2=0 -DFNDSA_SSE2=0 -DFNDSA_NEON=0
CFLAGS := -O2 -Wall -Wextra -ffunction-sections -fdata-sections
CXXFLAGS := $(CFLAGS) -std=c++17
CSRC := $(wildcard $(FN)/*.c) $(ML)/mlkem_native.c
OBJ := $(addprefix $(BUILD_DIR)/,$(notdir $(CSRC:.c=.o)))
.PHONY: all
all: $(BUILD_DIR)/pqc-proof
$(BUILD_DIR):
	mkdir -p $@
$(BUILD_DIR)/%.o: $(FN)/%.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
$(BUILD_DIR)/mlkem_native.o: $(ML)/mlkem_native.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
$(BUILD_DIR)/proof.o: $(PROOF)/pqc_proof.cpp $(PROOF)/pqc_proof.h $(PROOF)/pqc_crypto.h | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@
$(BUILD_DIR)/crypto.o: $(PROOF)/pqc_crypto.cpp $(PROOF)/pqc_crypto.h | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@
$(BUILD_DIR)/host.o: host.cpp $(PROOF)/pqc_proof.h $(PROOF)/pqc_crypto.h | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@
$(BUILD_DIR)/pqc-proof: $(OBJ) $(BUILD_DIR)/crypto.o $(BUILD_DIR)/proof.o $(BUILD_DIR)/host.o
	$(CXX) -Wl,--gc-sections $^ -lcrypto -o $@
