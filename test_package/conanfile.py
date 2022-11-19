from conans import ConanFile, CMake, tools
import os

class TestPackageConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake", "cmake_find_package"

    # # https://docs.conan.io/en/latest/reference/conanfile/methods.html#configure
    # def configure(self):
    #     # add "d" (if not exist) to "Visual Studio" compile runtime
    #     if settings["compiler"] == "Visual Studio" and settings["build_type"] == "Debug":
    #         if not settings["compiler.runtime"].endswith("d"):
    #             settings["compiler.runtime"] += "d"

    # # https://docs.conan.io/en/latest/reference/conanfile/methods.html#requirements
    # def requirements(self):
    #     self.requires("glib/2.69.1")

    # https://docs.conan.io/en/latest/reference/conanfile/methods.html#build
    def build(self):
        cmake = CMake(self)
        cmake.definitions["CONAN_DISABLE_CHECK_COMPILER"] = "True" # skip cheching compile version
        cmake.configure()
        cmake.build()

    # https://docs.conan.io/en/latest/reference/conanfile/methods.html#test
    def test(self):
        if not tools.cross_building(self.settings):
            bin_path = os.path.join(os.getcwd(), "bin", "test_package")
            self.output.info("bin_path: %s" % bin_path)
            self.run(bin_path, run_environment=True)