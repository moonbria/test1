function getCookie(name) {
    var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
    return r ? r[1] : undefined;
}


$(function () {

    $(".focused").click(function () {
        //  取消关注当前新闻作者
        var user_id = $(this).attr("data-userid")
        var params = {
            "action": "unfollow",
            "user_id": user_id
        }
        $.ajax({
            url: "news/followed_user",
            type: "post",
            contentType: "application/json",
            headers: {
                "X-CSRFToken": getCookie("csrf_token")
            },
            data: JSON.stringify(params),
            succeess: function (resp) {
                if (resp.errno == "0"){
                    // 取消關注成功
                    var count = parseInt($(".follows b").html());
                    count++;
                    $(".follows b").html(count + "")
                    $(".focus").hide()
                    $(".focused").show()
                }else if (resp.errno == "4101"){
                    //未登錄　彈出登陸框
                    $(".login_form_con").show();
                }else {
                    // 關注失敗
                    alert(resp.errmsg)
                }

            }
        })
    })
})



