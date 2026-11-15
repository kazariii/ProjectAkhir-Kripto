ROOT := $(abspath ../..)
BUILD_DIR ?= $(ROOT)/evidence/local/pqc-session-build
FN := $(ROOT)/firmware/lib/c-fn-dsa
ML := $(ROOT)/firmware/lib/mlkem-native
CORE := $(ROOT)/firmware/lib/pqc-proof/src
CPPFLAGS := -I$(FN) -I$(ML) -I$(CORE) -DMLK_CONFIG_PARAMETER_SET=512 -DMLK_CONFIG_NAMESPACE_PREFIX=pqc_mlkem -DMLK_CONFIG_NO_RANDOMIZED_API -DMLK_CONFIG_SERIAL_FIPS202_ONLY -DFNDSA_AVX2=0 -DFNDSA_SSE2=0 -DFNDSA_NEON=0
CFLAGS := -O2 -g -Wall -Wextra -Werror -Wno-unused-function -fPIC
CXXFLAGS := $(CFLAGS) -std=c++17
CSRC := $(wildcard $(FN)/*.c) $(ML)/mlkem_native.c
OBJ := $(addprefix $(BUILD_DIR)/,$(notdir $(CSRC:.c=.o)))
.PHONY: all test
all: $(BUILD_DIR)/libpqc-session.so $(BUILD_DIR)/session-test
$(BUILD_DIR):
	mkdir -p $@
$(BUILD_DIR)/%.o: $(FN)/%.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
$(BUILD_DIR)/mlkem_native.o: $(ML)/mlkem_native.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
$(BUILD_DIR)/crypto.o: $(CORE)/pqc_crypto.cpp $(CORE)/pqc_crypto.h | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@
$(BUILD_DIR)/session.o: $(CORE)/pqc_session.cpp $(CORE)/pqc_session.h $(CORE)/pqc_crypto.h | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@
$(BUILD_DIR)/native.o: native.cpp $(CORE)/pqc_session.h $(CORE)/pqc_crypto.h | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@
$(BUILD_DIR)/libpqc-session.so: $(OBJ) $(BUILD_DIR)/crypto.o $(BUILD_DIR)/session.o $(BUILD_DIR)/native.o
	$(CXX) -shared $^ -lcrypto -o $@
$(BUILD_DIR)/session-test: ../../tests/session_test.cpp $(BUILD_DIR)/libpqc-session.so
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< -L$(BUILD_DIR) -lpqc-session -Wl,-rpath,'$$ORIGIN' -o $@
test: all
	$(BUILD_DIR)/session-test
