TypeError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/mount/src/scionstr/app.py", line 117, in <module>
    total_ads = sp_grouped.add(sb_grouped, fill_value=0).reset_index()
                ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/frame.py", line 8371, in add
    return self._flex_arith_method(
           ~~~~~~~~~~~~~~~~~~~~~~~^
        other, operator.add, level=level, fill_value=fill_value, axis=axis
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/frame.py", line 8291, in _flex_arith_method
    new_data = self._combine_frame(other, op, fill_value)
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/frame.py", line 8033, in _combine_frame
    new_data = self._dispatch_frame_op(other, _arith_op)
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/frame.py", line 7978, in _dispatch_frame_op
    bm = self._mgr.operate_blockwise(
        # error: Argument 1 to "operate_blockwise" of "ArrayManager" has
    ...<6 lines>...
        array_op,
    )
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/internals/managers.py", line 1530, in operate_blockwise
    return operate_blockwise(self, other, array_op)
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/internals/ops.py", line 65, in operate_blockwise
    res_values = array_op(lvals, rvals)
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/frame.py", line 8031, in _arith_op
    return func(left, right)
